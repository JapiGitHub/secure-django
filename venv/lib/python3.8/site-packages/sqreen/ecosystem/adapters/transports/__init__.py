# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

from .botocore import BotocoreTransportAdapter
from .http_client import HttpClientTransportAdapter
from .kafka import KafkaTransportAdapter
from .mysqldb import MySQLDbTransportAdapter
from .pika import PikaTransportAdapter
from .psycopg2 import Psycopg2TransportAdapter
from .pymongo import PyMongoTransportAdapter
from .redis import RedisTransportAdapter
from .sqlite3 import SQLite3TransportAdapter


def init(interface_manager):
    """ Sqreen ecosystem transport adapters initialization
    """
    interface_manager.register(HttpClientTransportAdapter())
    interface_manager.register(MySQLDbTransportAdapter())
    interface_manager.register(Psycopg2TransportAdapter())
    interface_manager.register(PyMongoTransportAdapter())
    interface_manager.register(SQLite3TransportAdapter())
    interface_manager.register(RedisTransportAdapter())
    interface_manager.register(BotocoreTransportAdapter())
    interface_manager.register(KafkaTransportAdapter())
    interface_manager.register(PikaTransportAdapter())
