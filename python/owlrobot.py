#!/usr/bin/env python

# owlRobotics robot platform - Raspberry PI Python interface (using CAN bus hardware)

import ctypes
import struct
import os
import time
import math
import can   # pip install --break-system-packages  python-can


OWL_DRIVE_MSG_ID      = 300
MY_NODE_ID            = 60 

LEFT_MOTOR_NODE_ID    = 1
RIGHT_MOTOR_NODE_ID   = 2
TOOL_MOTOR_NODE_ID    = 3

LEFT_BACK_MOTOR_NODE_ID   = 1
RIGHT_BACK_MOTOR_NODE_ID  = 2
RIGHT_FRONT_MOTOR_NODE_ID = 3
LEFT_FRONT_MOTOR_NODE_ID  = 4


# what action to do...
can_cmd_info       = 0  # broadcast something
can_cmd_request    = 1  # request something
can_cmd_set        = 2  # set something
can_cmd_save       = 3  # save something        


# which variable to use for the action...
can_val_target          = 0   # target
can_val_voltage         = 1   # voltage
can_val_current         = 2   # current
can_val_velocity        = 3   # velocity
can_val_angle           = 4   # angle
can_val_motion_ctl_mode = 5   # motion control mode
can_val_cfg_mem         = 6   # config memory
can_val_motor_enable    = 7   # motor enable state
can_val_pAngleP         = 8   # angle P controller
can_val_velocityLimit   = 9   # max. velocity of the position control (rad/s)
can_val_pidVelocityP    = 10  # velocity P   
can_val_pidVelocityI    = 11  # velocity I   
can_val_pidVelocityD    = 12  # velocity D
can_val_pidVelocityRamp = 13  # velocity PID output ramp  (max. output change/s)
can_val_lpfVelocityTf   = 14  #  velocity low-pass filtering time constant (sec)
can_val_error           = 15  #  error status
can_val_upload_firmware = 16  #  upload file (to upload new firmware)
can_val_firmware_crc    = 17  #  firmware flash memory CRC (to verify firmware integrity)        
can_val_firmware_ver    = 18  # firmware version
can_val_broadcast_rx_enable  = 19  # broadcast receive enable state       
can_val_fifo_target     = 20   # add target (to drive within one clock duration) to FIFO 
can_val_endswitch_allow_pos_neg_dtargets = 21, # pos/neg delta targets allowed at end-switch?
can_val_reboot          = 22   # reboot MCU
can_val_endswitch       = 23   # end-switch status
can_val_fifo_clock      = 24   # FIFO clock signal (process FIFO)
can_val_control_error   = 25   # control error (setpoint-actual)
can_val_fifo_target_ack_result_val = 26, # which variable to send in an 'can_val_fifo_target' acknowledge     
can_val_detected_supply_voltage = 27,  # detected supply voltage
can_val_angle_add       = 28   # add angle 
can_val_pwm_speed       = 29   #pwm-speed (-1.0...1.0  =  classic motor controller compatiblity)
can_val_odo_ticks       = 30   # odometry ticks (encoder ticks   =  classic motor controller compatiblity)


# motor driver error values
err_ok           = 0  # everything OK
err_no_comm      = 1  # no CAN communication
err_no_settings  = 2  # no settings
err_undervoltage = 3  # undervoltage triggered
err_overvoltage  = 4  # overvoltage triggered
err_overcurrent  = 5  # overcurrent triggered
err_overtemp     = 6  # over-temperature triggered    


class CStruct(ctypes.LittleEndianStructure):
    _fields_ = [
        ("sourceId", ctypes.c_uint32, 6),  # 6 bit wide
        ("destId", ctypes.c_uint32, 6), # 6 bits wide
        ("reserved", ctypes.c_uint32, 4)   # 4 bits wide
    ]


# single robot motor class

class Motor():
    def __init__(self, aRobot, aNodeId, aName):
        self.nodeId = aNodeId
        self.robot = aRobot
        self.name = aName
        self.speed = 0.0
        print(self.name, ': motor object with nodeId', aNodeId)

    # rad/s
    def setSpeed(self, aSpeed):
        #print(self.name, ': speed', speed)
        self.speed = aSpeed
        self.robot.sendCanData(self.nodeId, can_cmd_set, can_val_velocity, struct.pack('<f', aSpeed))

    def getSpeed(self):
        return self.speed
    
    

# abstract robot class with forward and backward kinematics
# forward kinematics: obtains position and velocity of end effector (here: robot body), given the known joint angles 
# and angular velocities (here: motors).
# example:  motor velocities => body position and body velocity 

# inverse kinematics:  gives the joint velocities q' (here: motors) for a desired end-effector velocity X' (here: robot body)  
# example:  body velocity => motor velocities

# abstract drive system (differential wheel, mecanum wheel etc.)
#
# we use ROS coordinate axis (x is forward, y is left, z is up, CCW is positive):
# https://www.ros.org/reps/rep-0105.html
#
# top view (z up):
#
#        y
#        |
#    mobile base ----> x    (forward driving axis)
#
# angles:  counterclock-wise: positive (+) 


class Robot():
    def __init__(self, aname = "owlRobot"):
        self.name = aname        
        print(self.name, ': init')
        try:
            self.bus = can.interface.Bus(channel='can0', bustype='socketcan', receive_own_messages=True)
            #notifier = can.Notifier(self.bus, [can.Printer()])
        except:
            self.bus = None
            print('error opening CAN bus')
            pass

        # default wheel dimensions        
        self.wheelDiameter = 0          # wheel diameter (m) 
        self.wheelToBodyCenterX = 0     # wheel-axis to body center horizontal distance (m)
        self.wheelToBodyCenterY = 0     # wheel-axis to body center vertical distance (m)

        # -------- inverse kinematics (body velocity commands => motor velocities) -------------------------------
        self.cmdVelX = 0                # forward velocity command (m/s)
        self.cmdVelY = 0                # sideways velocity command (m/s)
        self.cmdVelTheta = 0            # rotational velocity command (rad/s) 

        # -------- forward kinematics (measured motor velocitities => body velocities) ----------------------------
        self.odoVelX = 0               # measured forward velocity (m/s)
        self.odoVelY = 0               # measured sideways velocity (m/s)
        self.odoVelTheta = 0           # measured rotational velocity (rad/s)
        self.odoX = 0                  # measured forward position (m)
        self.odoY = 0                  # measured sideways position (m)
        self.odoTheta = 0              # measured rotational position (rad)

        # bluetooth config
        self.bluetoothAddr = "F0:F1:F2:F3:F4:F5"
        self.bluetoothUSB = False
        
        # --------- motor ----------------------------------------------------------------------------------------
        self.toolMotor = Motor(self, TOOL_MOTOR_NODE_ID, 'toolMotor') 

        self.lastDriveTime = time.time()

    def print(self):
        print('odoX', round(self.odoX, 2), 'odoY', round(self.odoY, 2), 'odoTheta', round(self.odoTheta / math.pi * 180.0))

    def __del__(self):
        if self.bus is None: return
        print('closing CAN...')        
        self.bus.shutdown()


    def sendCanData(self, destNodeId, cmd, val, data):        
        if self.bus is None: return
        cs = CStruct()
        cs.sourceId = MY_NODE_ID
        cs.destId = destNodeId
        node = struct.unpack_from('<BB', cs)
        #print(node[0])
        
        frame = bytes(node) + bytes([cmd]) + bytes([val]) + data

        #print('sendCanData=', frame, 'sourceNodeId=', bin(MY_NODE_ID), 'destNodeId=', bin(destNodeId), 'cmd=', bin(cmd), 
        #    'val=', bin(val), 'data=', data)
        
        #for data in frame:
        #    print(bin(data))

        #frame = [0x7c,0xe0,0x02,0x1d,0x91,0x90,0x90,0xbd]

        msg = can.Message(arbitration_id=OWL_DRIVE_MSG_ID, data=frame, is_extended_id=False)
        #print(msg)
        self.bus.send(msg, timeout=0.2)


    # differential drive platform
    def motorSpeedDifferential(self, leftMotorSpeed, rightMotorSpeed, toolMotorSpeed):        
        self.sendCanData(LEFT_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', leftMotorSpeed))
        self.sendCanData(RIGHT_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', rightMotorSpeed))
        self.sendCanData(TOOL_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', toolMotorSpeed))

        #self.sendCanData(LEFT_MOTOR_NODE_ID, can_cmd_set, can_val_pwm_speed, struct.pack('<f', leftMotorSpeed))
        #self.sendCanData(RIGHT_MOTOR_NODE_ID, can_cmd_set, can_val_pwm_speed, struct.pack('<f', rightMotorSpeed))
        #self.sendCanData(TOOL_MOTOR_NODE_ID, can_cmd_set, can_val_pwm_speed, struct.pack('<f', toolMotorSpeed))


    # mecanum platform
    def motorSpeedMecanum(self, leftBackMotorSpeed, rightBackMotorSpeed, rightFrontMotorSpeed, leftFrontMotorSpeed):
        self.sendCanData(LEFT_BACK_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', leftBackMotorSpeed))
        self.sendCanData(RIGHT_BACK_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', rightBackMotorSpeed))
        self.sendCanData(RIGHT_FRONT_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', rightFrontMotorSpeed))
        self.sendCanData(LEFT_FRONT_MOTOR_NODE_ID, can_cmd_set, can_val_velocity, struct.pack('<f', leftFrontMotorSpeed))
    

    #  transfers body velocities into motor velocities
    #    set inverse kinematics (body velocities => motor velocities)
    #    x: forward velocity (m/s)
    #    y: sideways velocity (m/s)
    #    theta: rotational veloctiy (rad/s)
    def setRobotSpeed(vx, vy, oz):
        pass




if __name__ == "__main__":

    robot = Robot()

    while True:
        time.sleep(1.0)
        robot.motorSpeedDifferential(100.0, 100.0, 100.0)
        
    



