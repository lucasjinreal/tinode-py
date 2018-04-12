# -*- coding: utf-8 -*-
# file: gen_messages.py
# author: JinTian
# time: 11/04/2018 11:23 AM
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
import argparse
import base64
import grpc
import json
import random
import shlex
import sys
import os

import pbx.model_pb2 as pb
import pbx.model_pb2_grpc as pbx

APP_NAME = "elves-py"
VERSION = "0.14"

# Dictionary wich contains lambdas to be executed when server response is received
onCompletion = {}

# Saved topic: default topic name to make keyboard input easier
SavedTopic = None


def print_server_params(params):
    print("成功连接到服务器:")
    for p in params:
        print("\t" + p + ": " + json.loads(params[p]))


def read_cookie():
    try:
        cookie = open('elves-cookie', 'r')
        params = json.load(cookie)
        cookie.close()
        if params.get("token") is not None:
            return None
        return params

    except Exception as err:
        print("'elves-cookies'并不存在", err)
        return None


def save_cookie(params_):
    if params_ is None:
        return

    # Protobuf map 'params' is not a python object or dictionary. Convert it.
    nice = {}
    for p in params_:
        nice[p] = json.loads(params_[p])

    print("Authenticated as", nice.get('user'))

    try:
        cookie = open('elves-cookie', 'w')
        json.dump(nice, cookie)
        cookie.close()
    except Exception as err:
        print("Failed to save authentication cookie", err)


# Pack user's name and avatar into a vcard represented as json.
def make_vcard(fn, photofile):
    card = None

    if (fn is not None and fn.strip() != "") or photofile is not None:
        card = {}
        if fn is not None:
            card.fn = fn.strip()

        if photofile is not None:
            try:
                f = open(photofile, 'rb')
                # dataStart = imageDataUrl.indexOf(",")
                card.photo = {}
                card.photo.data = base64.b64encode(f.read())
                # File extension is used as a file type
                # TODO: use mimetype.guess_type(ext) instead
                card.photo.type = os.path.splitext(photofile)[1]
            except IOError as err:
                print("Error opening '" + photofile + "'", err)

        card = json.dumps(card)

    return card


# Constructing individual messages
def msg_hi(mid):
    onCompletion[str(mid)] = lambda params: print_server_params(params)
    return pb.ClientMsg(hi=pb.ClientHi(id=str(mid), user_agent=APP_NAME + "/" + VERSION + " gRPC-python",
                                       ver=VERSION, lang="EN"))


def msg_account(mid, user, scheme, secret, uname, password, do_login, tags, fn, photo, private, auth, anon):
    if secret is None and uname is not None:
        if password is None:
            password = ''
        secret = str(uname) + ":" + str(password)
    return pb.ClientMsg(acc=pb.ClientAcc(id=str(mid), user_id=user,
                                         scheme=scheme, secret=secret, login=do_login,
                                         tags=tags.split(",") if tags else None,
                                         desc=pb.SetDesc(default_acs=pb.DefaultAcsMode(auth=auth, anon=anon),
                                                         public=make_vcard(fn, photo), private=private)))


def msg_login(mid, scheme, secret, uname=None, password=None):
    if secret is None or secret == '' and uname is not None:
        if password is None:
            password = ''
        secret = str(uname) + ":" + str(password)
    onCompletion[str(mid)] = lambda params: save_cookie(params)
    return pb.ClientMsg(login=pb.ClientLogin(id=str(mid), scheme=scheme, secret=secret.encode('utf-8')))


def msg_get(mid, topic, desc, sub, data):
    what = []
    if desc:
        what.append("desc")
    if sub:
        what.append("sub")
    if data:
        what.append("data")
    return pb.ClientMsg(get=pb.ClientGet(id=str(mid), topic=topic,
                                         query=pb.GetQuery(what=" ".join(what))))


def msg_set(mid, topic, user, fn, photo, private, auth, anon, mode):
    return pb.ClientMsg(set=pb.ClientSet(id=str(mid), topic=topic,
                                         query=pb.SetQuery(
                                             desc=pb.SetDesc(default_acs=pb.DefaultAcsMode(auth=auth, anon=anon),
                                                             public=make_vcard(fn, photo), private=private),
                                             sub=pb.SetSub(user_id=user, mode=mode))))


def msg_delete(mid, topic, what, param, hard):
    if topic is None and param is not None:
        topic = param
        param = None

    print(mid, topic, what, param, hard)
    enum_what = None
    before = None
    seq_list = None
    user = None
    if what == 'msg':
        enum_what = pb.ClientDel.MSG
        if param == 'all':
            seq_list = [pb.DelQuery(range=pb.SeqRange(low=1, hi=0x8FFFFFF))]
        elif param is not None:
            seq_list = [pb.DelQuery(seq_id=int(x.strip())) for x in param.split(',')]
        print(seq_list)

    elif what == 'sub':
        enum_what = pb.ClientDel.SUB
        user = param
    elif what == 'topic':
        enum_what = pb.ClientDel.TOPIC

    # Field named 'del' conflicts with the keyword 'del. This is a work around.
    msg = pb.ClientMsg()
    xdel = getattr(msg, 'del')
    """
    setattr(msg, 'del', pb.ClientDel(id=str(id), topic=topic, what=enum_what, hard=hard,
        del_seq=seq_list, user_id=user))
    """
    xdel.id = str(mid)
    xdel.topic = topic
    xdel.what = enum_what
    if hard is not None:
        xdel.hard = hard
    if seq_list is not None:
        xdel.del_seq.extend(seq_list)
    if user is not None:
        xdel.user_id = user
    return msg


def msg_note(mid, topic, what, seq):
    enum_what = None
    if what == 'kp':
        enum_what = pb.KP
        seq = None
    elif what == 'read':
        enum_what = pb.READ
        seq = int(seq)
    elif what == 'recv':
        enum_what = pb.READ
        seq = int(seq)
    return pb.ClientMsg(note=pb.ClientNote(topic=topic, what=enum_what, seq_id=seq))
