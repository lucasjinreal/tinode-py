# -*- coding: utf-8 -*-
# file: elves_example.py
# author: JinTian
# time: 11/04/2018 11:56 AM
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
example to show how to using elves-py build chatbot server
"""
from elves import ElvesChatter


def main():
    elves = ElvesChatter(server_address='localhost:6061')
    elves.connect(listen='0.0.0.0:40051')
    elves.login(user_name='jintian', password='123456')
    elves.on_message()

if __name__ == '__main__':
    main()
