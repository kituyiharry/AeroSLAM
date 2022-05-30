#! /usr/bin/env python3

"""
Author: Harry Kituyi W <@kituyiharry>
Date  : October 2021

Simple PubSub workers with multiprocessing for ROSpy workers
"""

from abc import ABC
# I'll use processes to avoid the GIL
# https://the-fonz.gitlab.io/posts/python-multiprocessing/
# https://stackoverflow.com/a/57140017
from multiprocessing import Process, Manager, Queue, freeze_support, set_start_method
import time
import queue
import collections
from types import FunctionType
from typing import Dict, Generator, Union, Iterator
import rospy

# Msg abstraction passed between processes
Msg = collections.namedtuple('Msg', ['event', 'args'])
# Standard way to communicate state changes
State = collections.namedtuple('State', ['label', 'data'])
# Special wrapper for Msgs given to function handlers
HandlerMsg = collections.namedtuple('HandlerMsg', ['msg', 'slot', 'reactor'])

# TODO: Implement Stategraph to track state changes
# TODO: Implement broadcast Queue to broadcast State Messages (Termination ...)
class ProcState:

    """
    Handle states and changes
    Handles the mailbox (Keep Global and Local Queues -> Broadcast & targeted)
    """

    def __init__(self, initial_state=None):
        self._mailbox: Queue = Queue()       # Process local mailbox
        # NB: If the process changes, these become invalid
        self._refs: Dict[str, Queue] = {}    # Queue refs for other processes
        self._curstate: Union[State,None] = initial_state

    def linkto(self, name: str, reactor):
        """
        One way link to another process mailbox via its name
        """
        self._refs[name] = reactor._mailbox

    def receive(self):
        """
        Listen for messages, Return if none are present
        """
        msg = None
        try:
           msg = self._mailbox.get(timeout=0.005)
        except TimeoutError:
            pass
        except queue.Empty:
            pass
        return msg

    def send(self, to: str, eventname: str, args: State):
        """
        Send messages to a process. Silently drops if mailboxes are full
        """
        try:
            self._refs[to].put(Msg(eventname, args))
        except ValueError:
            # Sender not linked
            pass
        except queue.Full:
            # Messages will be dropped
            pass

    def curstate(self):
        """
        Returns the current internal state of the Process
        """
        return self._curstate

    def set_curstate(self, newstate: Union[State,None]):
        """
        Set the current state
        """
        self._curstate = newstate

class BaseHandler(ABC):

    def __init__(self, **kwargs):
        """
        Build the publisher or subscriber
        name: name of the node
        topic: topic to sub or pub
        msg: MSG class
        handler: Function to handle a message
        """
        self._name: str = kwargs.pop('name')
        self._topic: str = kwargs.pop('topic')
        self._msg: type = kwargs.pop('msgtype')
        self._handler: FunctionType = kwargs.pop('handler')
        self._reactor: ProcState = ProcState()

    def link(self, other):
        self._reactor.linkto(other._name, other._reactor)


    def reactor(self):
        return self._reactor

    def loop(self):
        """
        Run the mainloop
        """
        raise NotImplementedError()

    def onmessage(self, item=None):
        """
        How to handle or build a message
        """
        raise NotImplementedError()

    def _connect(self):
        """
        How to connection
        """
        raise NotImplementedError()


class ROSPublisher(BaseHandler):

    """
    ROS Publisher
    """

    def __init__(self, gensrc: Union[Generator, Iterator], rate: int = 2, queue_size: int = 10, **kwargs):
        """
        gensrc: Generator object for input messages
        rate: rate at which messages will be published to the topic
        msgbuilder: callback to build the data from the class
                    takes a tuple of msg and the next generator yield
        """
        BaseHandler.__init__(self, **kwargs)
        self._gen = gensrc
        self._rate = rate
        self._queue = queue_size

    def loop(self):
        """
        Start the 'eventloop' to communicate with ROS
        Initializes a dummy message that can be reused

        item = Msg,Worker
        """
        pub = self._connect()
        msg = self._msg()
        rospy.init_node(self._name)
        rate = rospy.Rate(self._rate)
        i = 0
        try:
            while not rospy.is_shutdown():
                i = i+1
                self._onmessage((msg, pub))
                rate.sleep()
        except StopIteration as err:
            rospy.loginfo(
                    "{} -> {} :: Generator consumed => {}".format(
                        self._name, self._topic, err.value
                        )
                    )
        except rospy.ROSInterruptException as err:
            rospy.loginfo(
                    "{} -> {} :: Received ROS interrupt => {}".format(
                        self._name, self._topic, err
                        )
                    )
        except Exception as err:
            rospy.logerr(
                    "{} -> {} :: Unhandled termination => {}".format(
                        self._name, self._topic, err
                        )
                    )

    def _connect(self):
        pub = rospy.Publisher(self._topic, self._msg, queue_size=self._queue)
        return pub

    def _onmessage(self, item):
        """
        Build the message for publishing
        NB: Override for custom logic if needed
        """
        msg, pub = item
        pmsg = self._handler(HandlerMsg(msg, next(self._gen), self._reactor))
        if pmsg != None:
            pub.publish(pmsg)
        return msg


class ROSSubscriber(BaseHandler):

    """
    ROS Subscriber
    """

    def __init__(self, **kwargs):
        """
        ROS Subscriber
        """
        BaseHandler.__init__(self, **kwargs)

    def loop(self):
        """
        Handle messages here

        item = Msg
        """
        self._connect()
        rospy.init_node(self._name)
        rospy.spin()
        rospy.loginfo(
                "{} -> {} :: Subscriber terminated ".format(
                    self._name, self._topic
                    )
                )

    def _connect(self):
        sub = rospy.Subscriber(
            self._topic, self._msg, callback=lambda m: self.onmessage(m)
        )
        return sub

    def onmessage(self, msg):
        """
        Handle messages from remote and IPC
        """
        self._handler(HandlerMsg(msg, None, self._reactor))


class Worker(Process):

    """
    Resolve scopes and starts the process

    In multiprocessing, processes  are spawned by creating  a Process object
    and  then  calling  its  start()  method. Process  follows  the  API  of
    threading.Thread.

    """

    def __init__(self, handler):
        Process.__init__(self)
        self._roshandler: BaseHandler = handler

    def run(self):
        """
        Process override that does tha main loop
        """
        self._roshandler.loop()

# TODO: Hold processess in a Supervision tree or graph of Sorts
class BaseRuntime:

    """
    Parses and Spins multiple workers
    """

    def __init__(self):
        """
        Runtime
        """
        self._procs: list[Worker] = []
        self._manager = Manager()

    def add(self, worker: Worker):
        """
        Add a worker to be started
        """
        self._procs.append(worker)

    def extend(self, workerlist: list[Worker]):
        """
        extend with a list of Workers
        """
        self._procs.extend(workerlist)

    def getmanager(self):
        """
        Manager can be used for creating shared vars, IPC
        """
        return self._manager

    def startsync(self, method=None):
        """
        Start workers synchronously
        Select a process strategy.
        Call within `if name == __main__`
        ref: https://docs.python.org/3/library/multiprocessing.html#the-process-class
        """
        freeze_support()
        if method is not None:
            set_start_method(method)
        with self._manager:
            # mailbox = self._manager.Queue()
            for proc in self._procs:
                # proc._roshandler._ipc = mailbox
                proc.start()
            self.__waitalive()

    def __waitalive(self):
        """
        Keeps the main thread active
        """
        states = list(map(lambda p: p.is_alive(), self._procs))
        while any(states):
            time.sleep(2)
            states = list(map(lambda p: p.is_alive(), self._procs))
