# -*- coding: utf-8 -*-
from __future__ import absolute_import

import inject
import paho.mqtt.client as mqtt
import rospy

from .bridge import create_bridge
from .mqtt_client import create_private_path_extractor
from .util import lookup_object

topic_list=[]

def create_config(mqtt_client, serializer, deserializer, mqtt_private_path):
    if isinstance(serializer, basestring):
        serializer = lookup_object(serializer)
    if isinstance(deserializer, basestring):
        deserializer = lookup_object(deserializer)
    private_path_extractor = create_private_path_extractor(mqtt_private_path)
    def config(binder):
        binder.bind('serializer', serializer)
        binder.bind('deserializer', deserializer)
        binder.bind(mqtt.Client, mqtt_client)
        binder.bind('mqtt_private_path_extractor', private_path_extractor)
    return config


def mqtt_bridge_node():
    # init node
    rospy.init_node('mqtt_bridge_node')

    # load parameters
    params = rospy.get_param("~", {})
    mqtt_params = params.pop("mqtt", {})
    conn_params = mqtt_params.pop("connection")
    mqtt_private_path = mqtt_params.pop("private_path", "")
    bridge_params = params.get("bridge", [])

    # create mqtt client
    mqtt_client_factory_name = rospy.get_param(
        "~mqtt_client_factory", ".mqtt_client:default_mqtt_client_factory")
    mqtt_client_factory = lookup_object(mqtt_client_factory_name)
    mqtt_client = mqtt_client_factory(mqtt_params)

    # load serializer and deserializer
    serializer = params.get('serializer', 'json:dumps')
    deserializer = params.get('deserializer', 'json:loads')

    # dependency injection
    config = create_config(
        mqtt_client, serializer, deserializer, mqtt_private_path)
    inject.configure(config)

    # configure and connect to MQTT broker
    mqtt_client.on_connect = _on_connect
    mqtt_client.on_disconnect = _on_disconnect
    mqtt_client.on_subscribe = _on_subscribe
    # mqtt_client.on_log = _on_log
    try:
        mqtt_client.connect(**conn_params)
    except:
        print "MQTT connect failed"

    # configure bridges
    bridges = []
    for bridge_args in bridge_params:
        bridges.append(create_bridge(**bridge_args))
        if bridge_args["factory"] == "mqtt_bridge.bridge:MqttToRosBridge":
            topic_list.append(bridges[-1]._topic_from)

    # start MQTT loop
    mqtt_client.loop_start()

    # register shutdown callback and spin
    rospy.on_shutdown(mqtt_client.disconnect)
    rospy.on_shutdown(mqtt_client.loop_stop)
    rospy.spin()


def _on_connect(client, userdata, flags, response_code):
    rospy.loginfo('MQTT connected: ' + str(response_code))
    for topic in topic_list:
        client.subscribe(topic, qos=1)

def _on_disconnect(client, userdata, response_code):
    rospy.loginfo('MQTT disconnected: ' + str(response_code))

def _on_subscribe(client, userdata, mid, granted_qos): 
    rospy.loginfo("subscribed: %s, granted_qos: %s" , mid, granted_qos)

def _on_log(client, userdata, level, buf): 
    rospy.loginfo("log_level: %d, buf: %s" , level, buf)

__all__ = ['mqtt_bridge_node']
