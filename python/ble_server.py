#!/usr/bin/env python

# owlRobotics robot platform example code:   Bluetooth Low Energy Server (use Dabble App joystick to control motors)

import owlrobot
import time
import dabble

 
app = dabble.Dabble('hci-socket:0')
#app = dabble.Dabble('usb:0')
robot = owlrobot.Robot()

MAX_SPEED = 100.0  # rpm


print('press CTRL+C to exit...')

toolMotorSpeed = 0

while True:
    if not dabble.connected: continue    
    #print('.', end="", flush=True)
    
    if app.extraButton == 'triangle':
        MAX_SPEED = 300.0
    elif app.extraButton == 'cross':
        MAX_SPEED = 100.0
    elif app.extraButton == 'circle':
        if toolMotorSpeed < 100:            
            toolMotorSpeeed = 100
        elif toolMotorSpeed < 200:
            toolMotorSpeeed = 200
        else: toolMotorSpeed = 0
        print('toolMotorSpeed', toolMotorSpeed)


    if app.analogMode:
        if app.y_value >= 0:
            speedLeft = (app.y_value + app.x_value*0.3) * MAX_SPEED
            speedRight = (app.y_value - app.x_value*0.3) * MAX_SPEED
        else:
            speedLeft = (app.y_value - app.x_value*0.3) * MAX_SPEED
            speedRight = (app.y_value + app.x_value*0.3) * MAX_SPEED            
        robot.motorSpeed(-speedLeft, speedRight, toolMotorSpeed)

    else:
        if app.joystickButton == 'up':
            robot.motorSpeed(-MAX_SPEED, MAX_SPEED, toolMotorSpeed)

        elif app.joystickButton == 'down':        
            robot.motorSpeed(MAX_SPEED, -MAX_SPEED, toolMotorSpeed)

        elif app.joystickButton == 'right':        
            robot.motorSpeed(-MAX_SPEED, -MAX_SPEED, toolMotorSpeed)

        elif app.joystickButton == 'left':        
            robot.motorSpeed(MAX_SPEED, MAX_SPEED, toolMotorSpeed)

        elif app.joystickButton == 'released':
            robot.motorSpeed(0, 0, 0)


    time.sleep(0.1)





