#! /usr/bin/env python3
import random
import simsim as Sim
import rospy
from nav_msgs.msg import Odometry
from std_msgs.msg import Int16


ODOM = "aerial_manipulator_odo"
TELE = "aerial_manipulator_tele"
KINO = "kinov"

# 2 forwards and downs 
uavmsgs = [ 7, 7, 4, 4, 4 ]

# 8 grip turns, 4 joint turns on signal and grip
armmsgs = [ 13, 13, 13, 13, 13, 13, 13, 13 , 3,3,3,3, 16 ]


def randgen():
    while True:
        yield random.choice(range(1, 9))

def buildmsg(msg, val, reactor):
    # print("Sent {} !!".format(val))
    msg.data = val
    return msg

def armwork():
    while True:
        yield random.choice(range(1,16))

def handleARM(m: Sim.HandlerMsg):
    m.msg.data =  m.slot
    return m.msg

def handleUAV(m: Sim.HandlerMsg):
    m.msg.data =  m.slot
    return m.msg

if __name__ == '__main__':

    armmsg = armwork()

    sub = Sim.ROSSubscriber(
            name=ODOM,
            topic="harrierD7/odometry_sensor1/odometry",
            msgtype=Odometry,
            handler=lambda hmsg: rospy.loginfo("X: {} && Y: {}".format(
                        hmsg.msg.pose.pose.position.x, hmsg.msg.pose.pose.position.y
                    )
                )
            )

    pub = Sim.ROSPublisher(
            gensrc=iter(uavmsgs),
            rate=1,
            name=TELE,
            topic="harrierD7/teleoperator",
            msgtype=Int16,
            handler=handleUAV
        )


    kin = Sim.ROSPublisher(
            gensrc=iter(armmsgs),
            rate=3,
            name=KINO,
            topic="/harrierD7/kinovaOper",
            msgtype=Int16,
            handler=handleARM
        )

    pub.link(sub)

    s = Sim.Worker(sub)
    p = Sim.Worker(pub)
    k = Sim.Worker(kin)
    r = Sim.BaseRuntime()
    r.extend([p, s, k])
    r.startsync()

