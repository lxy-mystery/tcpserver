#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import struct
import time
import uuid
import logging as log
from config import config

class Session:
    def __init__(self, connection, address):
        self._id = uuid.uuid1().hex
        self._connection = connection
        self._ip, self._port = address
        self._message = {}
        self._processer = {}
        self._left_recved = 0
        self._current_message = {}

    def init(self):
        #self.register(0x00, self.echo)
        self.register(0x02, self.heartbeat)
        log.basicConfig(filename=config["log"]["file"], level=config["log"]["level"], format=config["log"]["format"])

    def echo(self, sequence):
        log.info(f'[{sequence}][0][req]{self._message[sequence]["request"]["body"]}')
        return True, self._message[sequence]["request"]["body"]

    def heartbeat(self, sequence):
        log.info(f'[{sequence}][2][req]{self._message[sequence]["request"]["body"]}')
        return True, str(round(time.time() * 1000))

    def register(self, command, processer):
        self._processer[command] = processer

    def _parseHeader(self, header):
        log.info("::::recv header:{}".format(header))
        if len(header) < 16:
            log.warn("recv header:{} length less than 16".format(header))
            return None, None, None
        (begin_1, begin_2, command, length,
         sequence) = struct.unpack('<ccHIQ', header)
        log.info(f"::::decode header: {begin_1}, {begin_2}, {command}, {length}, {sequence}")
        if begin_1 != b'C' and begin_2 != b'X':
            log.warn("decode header:{} begin magic ({}, {}) check failed".format(header, begin_1, begin_2))
            return None, None, None
        return command, sequence, length

    def processCommand(self, command, sequence):
        if(command not in self._processer):
            log.warn("command:{} not found!".format(command))
            return False, None
        return self._processer[command](sequence)

    def doRequest(self):
        if self._left_recved > 0:
            # incomplete body, continue recv body
            msg = self._connection.recv(self._left_recved).decode("gbk")
            self._current_message["body"] = self._current_message["body"] + msg
            self._left_recved = self._left_recved - len(msg)
            sequence = self._current_message["sequence"]
            if self._left_recved > 0:
                log.info("incomplete body2" + str(sequence))
                return len(msg) > 0
            self._message[sequence] = {}
            self._message[sequence]['expire'] = round(time.time() * 1000) + 30 * 1000       # this message 30 seconds expired
            self._message[sequence]['request'] = {}
            self._message[sequence]['request']['command'] = self._current_message["command"]
            self._message[sequence]['request']['body'] = self._current_message["body"]
        else:
            # new request
            command, sequence, length = self._parseHeader(self._connection.recv(16))
            if command is None:
                return False
            body = self._connection.recv(length).decode("gbk")
            self._current_message["command"] = command
            self._current_message["sequence"] = sequence
            self._current_message["body"] = body
            self._left_recved = length - len(body)
            # incomplete should continue
            if self._left_recved > 0:
                log.info("incomplete body1:" + str(sequence))
                return len(body) > 0

        # complete package process it
        sequence = self._current_message["sequence"]
        body = self._current_message["body"]
        command = self._current_message["command"]
        self._message[sequence] = {}
        self._message[sequence]['expire'] = round(time.time() * 1000) + 30 * 1000       # this message 30 seconds expired
        self._message[sequence]['request'] = {}
        self._message[sequence]['request']['command'] = command
        self._message[sequence]['request']['body'] = body
        (result, response) = self.processCommand(command, sequence)
        log.info(f"[{sequence}][{command}]: {result} {response}")
        if response == "ip is invalid":
            del self._message[sequence]
            return True
        self._message[sequence]['response'] = {}
        self._message[sequence]['response']['data'] = response
        self._message[sequence]['response']['result'] = result
        return len(body) > 0

    def doResponse(self):
        log.debug("Response data")
        for sequence in list(self._message.keys()):
            message = self._message[sequence]
            if "response" in message and message["response"]["result"] and not message["response"]["data"] is None:
                data_length = len(message["response"]["data"])
                format = '<ccHIQ{}s'.format(data_length)
                response = struct.pack(
                    format, b'C', b'X', message['request']['command'], data_length, sequence, message['response']['data'].encode("GBK"))
                log.info(f"[{sequence} response : {response}")
                self._connection.send(response)
                del self._message[sequence]
            elif message['expire'] <= round(time.time() * 1000):
                log.warn("message [%s] is expired by %d" % (message['request']['body'], message['expire']))
                del self._message[sequence]

    def doConnect(self):
        log.warn("Connecting from:(%s:%d)" % (self._ip, self._port))
        self.init()

    def close(self, reason):
        log.warn("Closing connection (%s:%d) reason:%s" % (self._ip, self._port, str(reason)))
        self._connection.close()
