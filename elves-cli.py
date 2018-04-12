"""The Python implementation of the gRPC Tinode client."""

import argparse
import base64
import grpc
import json
import random
import shlex
import sys

from google.protobuf import json_format
from gen_messages import *

APP_NAME = "tn-cli"
VERSION = "0.14"

# Dictionary wich contains lambdas to be executed when server response is received
onCompletion = {}

# Saved topic: default topic name to make keyboard input easier
SavedTopic = None


def parse_cmd(cmd):
    """Parses command line input into a dictionary"""
    parts = shlex.split(cmd)
    parser = None
    if parts[0] == "acc":
        parser = argparse.ArgumentParser(prog=parts[0], description='Create or alter an account')
        parser.add_argument('--user', default=None, help='ID of the account to update')
        parser.add_argument('--scheme', default="basic", help='authentication scheme, default=basic')
        parser.add_argument('--secret', default=None, help='secret for authentication')
        parser.add_argument('--uname', default=None, help='user name for basic authentication')
        parser.add_argument('--password', default=None, help='password for basic authentication')
        parser.add_argument('--do-login', action='store_true', help='login with the newly created account')
        parser.add_argument('--tags', action=None, help='tags for user discovery, comma separated list without spaces')
        parser.add_argument('--fn', default=None, help='user\'s human name')
        parser.add_argument('--photo', default=None, help='avatar file name')
        parser.add_argument('--private', default=None, help='user\'s private info')
        parser.add_argument('--auth', default=None, help='default access mode for authenticated users')
        parser.add_argument('--anon', default=None, help='default access mode for anonymous users')
    elif parts[0] == "login":
        parser = argparse.ArgumentParser(prog=parts[0], description='Authenticate current session')
        parser.add_argument('--scheme', default="basic")
        parser.add_argument('secret', nargs='?', default=argparse.SUPPRESS)
        parser.add_argument('--secret', dest='secret', default=None)
        parser.add_argument('--uname', default=None)
        parser.add_argument('--password', default=None)
    elif parts[0] == "sub":
        parser = argparse.ArgumentParser(prog=parts[0], description='Subscribe to topic')
        parser.add_argument('topic', nargs='?', default=argparse.SUPPRESS, help='topic to subscribe to')
        parser.add_argument('--topic', dest='topic', default=None, help='topic to subscribe to')
        parser.add_argument('--fn', default=None, help='topic\'s user-visible name')
        parser.add_argument('--photo', default=None, help='avatar file name')
        parser.add_argument('--private', default=None, help='topic\'s private info')
        parser.add_argument('--auth', default=None, help='default access mode for authenticated users')
        parser.add_argument('--anon', default=None, help='default access mode for anonymous users')
        parser.add_argument('--get-query', default=None, help='query for topic metadata or messages')
    elif parts[0] == "leave":
        parser = argparse.ArgumentParser(prog=parts[0], description='Detach or unsubscribe from topic')
        parser.add_argument('topic', nargs='?', default=argparse.SUPPRESS, help='topic to detach from')
        parser.add_argument('--topic', dest='topic', default=None, help='topic to detach from')
        parser.add_argument('--unsub', action='store_true', help='detach and unsubscribe from topic')
    elif parts[0] == "pub":
        parser = argparse.ArgumentParser(prog=parts[0], description='Send message to topic')
        parser.add_argument('topic', nargs='?', default=argparse.SUPPRESS, help='topic to publish to')
        parser.add_argument('--topic', dest='topic', default=None, help='topic to publish to')
        parser.add_argument('content', nargs='?', default=argparse.SUPPRESS, help='message to send')
        parser.add_argument('--content', dest='content', help='message to send')
    elif parts[0] == "get":
        parser = argparse.ArgumentParser(prog=parts[0], description='Query topic for messages or metadata')
        parser.add_argument('topic', nargs='?', default=argparse.SUPPRESS, help='topic to update')
        parser.add_argument('--topic', dest='topic', default=None, help='topic to update')
        parser.add_argument('--desc', action='store_true', help='query topic description')
        parser.add_argument('--sub', action='store_true', help='query topic subscriptions')
        parser.add_argument('--data', action='store_true', help='query topic messages')
    elif parts[0] == "set":
        parser = argparse.ArgumentParser(prog=parts[0], description='Update topic metadata')
        parser.add_argument('topic', help='topic to update')
        parser.add_argument('--fn', default=None, help='topic\'s name')
        parser.add_argument('--photo', default=None, help='avatar file name')
        parser.add_argument('--private', default=None, help='topic\'s private info')
        parser.add_argument('--auth', default=None, help='default access mode for authenticated users')
        parser.add_argument('--anon', default=None, help='default access mode for anonymous users')
        parser.add_argument('--user', default=None, help='ID of the account to update')
        parser.add_argument('--mode', default=None, help='new value of access mode')
    elif parts[0] == "del":
        parser = argparse.ArgumentParser(prog=parts[0], description='Delete message(s), subscription or topic')
        parser.add_argument('topic', nargs='?', default=argparse.SUPPRESS, help='topic being affected')
        parser.add_argument('--topic', dest='topic', default=None, help='topic being affected')
        parser.add_argument('what', default='msg', choices=('msg', 'sub', 'topic'),
                            help='what to delete')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--user', dest='param', help='delete subscription with the given user id')
        group.add_argument('--list', dest='param', help='comma separated list of message IDs to delete')
        parser.add_argument('--hard', action='store_true', help='hard-delete messages')
    elif parts[0] == "note":
        parser = argparse.ArgumentParser(prog=parts[0], description='Send notification to topic, ex "note kp"')
        parser.add_argument('topic', help='topic to notify')
        parser.add_argument('what', nargs='?', default='kp', const='kp', choices=['kp', 'read', 'recv'],
                            help='notification type')
        parser.add_argument('--seq', help='value being reported')
    else:
        print("Unrecognized:", parts[0])
        print("Possible commands:")
        print("\tacc\t- create account")
        print("\tlogin\t- authenticate")
        print("\tsub\t- subscribe to topic")
        print("\tleave\t- detach or unsubscribe from topic")
        print("\tpub\t- post message to topic")
        print("\tget\t- query topic for metadata or messages")
        print("\tset\t- update topic metadata")
        print("\tdel\t- delete message(s), topic or subscription")
        print("\tnote\t- send notification")
        print("\n\tType <command> -h for help")
        return None

    try:
        args = parser.parse_args(parts[1:])
        args.cmd = parts[0]
        return args
    except SystemExit:
        return None


def serialize_cmd(string, mid):
    """Take string read from the command line, convert in into a protobuf message"""

    # Convert string into a dictionary
    cmd = parse_cmd(string)
    if cmd is None:
        return None

    # Process dictionary
    if cmd.cmd == "acc":
        return msg_account(mid, cmd.user, cmd.scheme, cmd.secret, cmd.uname, cmd.password,
                           cmd.do_login, cmd.tags, cmd.fn, cmd.photo, cmd.private, cmd.auth, cmd.anon)
    elif cmd.cmd == "login":
        return msg_login(mid, cmd.scheme, cmd.secret, cmd.uname, cmd.password)
    elif cmd.cmd == "sub":
        return pb.ClientMsg(sub=pb.ClientSub(id=str(mid), topic=cmd.topic))
    elif cmd.cmd == "leave":
        return pb.ClientMsg(leave=pb.ClientLeave(id=str(mid), topic=cmd.topic))
    elif cmd.cmd == "pub":
        return pb.ClientMsg(pub=pb.ClientPub(id=str(mid), topic=cmd.topic, no_echo=True,
                                             content=json.dumps(cmd.content)))
    elif cmd.cmd == "get":
        return msg_get(mid, cmd.topic, cmd.desc, cmd.sub, cmd.data)
    elif cmd.cmd == "set":
        return msg_set(mid, cmd.topic, cmd.user, cmd.fn, cmd.photo, cmd.private, cmd.auth, cmd.anon, cmd.mode)
    elif cmd.cmd == "del":
        return msg_delete(mid, cmd.topic, cmd.what, cmd.param, cmd.hard)
    elif cmd.cmd == "note":
        return msg_note(mid, cmd.topic, cmd.what, cmd.seq)
    else:
        print(("Unrecognized: " + cmd.cmd))
        return None


def gen_message(schema, secret):
    """Client message generator: reads user input as string,
    converts to pb.ClientMsg, and yields"""

    random.seed()
    rid = random.randint(10000, 60000)

    yield msg_hi(rid)

    if schema is not None:
        rid += 1
        yield msg_login(rid, schema, secret)

    while True:
        rid += 1
        inp = input("tn> ")
        if inp == "":
            continue
        if inp == "exit" or inp == "quit":
            return
        cmd = serialize_cmd(inp, rid)
        if cmd is not None:
            yield cmd


def run(addr, schema, secret):
    channel = grpc.insecure_channel(addr)
    stub = pbx.NodeStub(channel)
    # Call the server
    stream = stub.MessageLoop(gen_message(schema, secret))
    try:
        # Read server responses
        for msg in stream:
            if msg.HasField("ctrl"):
                # Run code on command completion
                func = onCompletion.get(msg.ctrl.id)
                if func is not None:
                    del onCompletion[msg.ctrl.id]
                    if 200 <= msg.ctrl.code < 400:
                        func(msg.ctrl.params)
                print(str(msg.ctrl.code) + " " + msg.ctrl.text)
            elif msg.HasField("data"):
                print("\n收到消息: " + msg.data.from_user_id + ":\n")
                print(json.loads(msg.data.content) + "\n")
            elif msg.HasField("pres"):
                pass
            else:
                print("Message type not handled", msg)

    except grpc._channel._Rendezvous as err:
        print(err)


if __name__ == '__main__':
    """Parse command-line arguments. Extract host name and authentication scheme, if one is provided"""
    purpose = "Tinode command line client. Version " + VERSION + "."
    print(purpose)
    parser = argparse.ArgumentParser(description=purpose)
    parser.add_argument('--host', default='localhost:6061', help='address of Tinode server')
    parser.add_argument('--login-basic', help='login using basic authentication username:password')
    parser.add_argument('--login-token', help='login using token authentication')
    parser.add_argument('--login-cookie', action='store_true',
                        help='read token from cookie file and use it for authentication')
    args = parser.parse_args()

    print("Server '" + args.host + "'")

    schema = None
    secret = None
    if args.login_cookie:
        """Try reading cookie file"""
        params = read_cookie()
        if params is not None:
            schema = 'token'
            secret = base64.b64decode(params.get('token').encode('ascii'))

    if schema is None and args.login_token is not None:
        """Use token to login"""
        schema = 'token'
        secret = args.login_token

    if schema is None and args.login_basic is not None:
        """Use username:password"""
        schema = 'basic'
        secret = args.login_basic

    run(args.host, schema, secret)
