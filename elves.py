# -*- coding: utf-8 -*-
# file: elves.py
# author: JinTian
# time: 11/04/2018 11:37 AM
# Copyright 2018 JinTian. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------
"""
this file provide method for login register and on message listening methods
"""
from gen_messages import *
import queue
from concurrent import futures


class Plugin(pbx.PluginServicer):
    def Account(self, acc_event, context):
        action = None
        if acc_event.action == pb.CREATE:
            action = "created"
        elif acc_event.action == pb.UPDATE:
            action = "updated"
        elif acc_event.action == pb.DELETE:
            action = "deleted"
        else:
            action = "unknown"

        print("Account", action, ":", acc_event.user_id, acc_event.public)

        # TODO: subscribe to the new user.

        return pb.Unused()


class ElvesChatter(object):
    def __init__(self, server_address):
        self.server_address = server_address
        self.stub = None
        self.stream = None

        self.server = None

        self.queue_out = queue.Queue()
        self.mid = random.randint(10000, 60000)

    def next_id(self):
        self.mid += 1
        return str(self.mid)

    # ---------------- initial work -------------------
    def connect(self):
        self.init_server()
        print('=> server initialized.')
        self.init_client()
        print('=> client initialized.')

    def init_server(self):
        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=16))
        pbx.add_PluginServicer_to_server(Plugin(), self.server)
        self.server.add_insecure_port(self.server_address)
        self.server.start()

    def init_client(self):
        channel = grpc.insecure_channel(self.server_address)
        self.stub = pbx.NodeStub(channel)
        # Call the server
        print('=> init client will send an iterator to MessageLoop')
        self.stream = self.stub.MessageLoop(self.msg_iter())
        self.client_post(self.hello())
        # self.client_post(subscribe('me'))

    # ---------------- initial work -------------------

    def msg_iter(self):
        while True:
            msg = self.queue_out.get()
            print('-- get one msg out from queue: ', msg)
            if msg is None:
                return
            yield msg

    def register(self):
        pass

    def hello(self):
        tid = self.next_id()
        return pb.ClientMsg(hi=pb.ClientHi(id=tid, user_agent=APP_NAME + "/" + VERSION + " gRPC-python",
                                           ver=VERSION, lang="EN"))

    def login(self, user_name, password):
        self.client_post(msg_login(mid=self.next_id(), scheme='basic', secret='', uname=user_name, password=password))

    def publish(self, topic, text):
        mid = self.next_id()
        self.client_post(pb.ClientMsg(pub=pb.ClientPub(id=mid, topic=topic, no_echo=True,
                                                       content=json.dumps(text, ensure_ascii=False).encode('utf-8'))))

    def client_post(self, msg):
        self.queue_out.put(msg)

    @staticmethod
    def note_read(topic, seq):
        return pb.ClientMsg(note=pb.ClientNote(topic=topic, what=pb.READ, seq_id=seq))

    def on_message(self):
        try:
            # Read server responses
            if self.stream:
                print('raw message: ', self.stream)

                for msg in self.stream:
                    if msg.HasField("ctrl"):
                        # Run code on command completion
                        func = onCompletion.get(msg.ctrl.id)
                        if func is not None:
                            del onCompletion[msg.ctrl.id]
                            if 200 <= msg.ctrl.code < 400:
                                func(msg.ctrl.params)
                        print('got situation: ' + str(msg.ctrl.code) + " " + msg.ctrl.text)
                    elif msg.HasField("data"):
                        in_msg = msg.data.content.decode('utf-8')
                        print("收到消息: " + in_msg)
                        # here is the inference
                        self.publish(msg.data.topic, '我知道你再说： ' + in_msg)
                    elif msg.HasField("pres"):
                        pass
                    else:
                        print("Message type not handled", msg)
            else:
                print('还没有登录， call login() first.')
                exit()

        except Exception as err:
            print('some error: ', err)
