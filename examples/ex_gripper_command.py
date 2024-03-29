#!/usr/bin/env python3
"""
Example of interacting with the gripper.
`ros2 run pymoveit2 ex_gripper_command.py --ros-args -p action:="toggle"`
`ros2 run pymoveit2 ex_gripper_command.py --ros-args -p action:="open"`
`ros2 run pymoveit2 ex_gripper_command.py --ros-args -p action:="close"`
"""

from threading import Thread

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node

from pymoveit2 import GripperCommand
from pymoveit2.robots import pepper_robot


def main(args=None):

    rclpy.init(args=args)

    # Create node for this example
    node = Node("ex_gripper_command")

    # Declare parameter for joint positions
    node.declare_parameter(
        "action",
        "toggle",
    )

    # Create callback group that allows execution of callbacks in parallel without restrictions
    callback_group = ReentrantCallbackGroup()

    # Create MoveIt 2 gripper interface
    moveit2_gripper = GripperCommand(
        node=node,
        gripper_joint_names=pepper_robot.gripper_joint_names(),
        open_gripper_joint_positions=pepper_robot.OPEN_GRIPPER_JOINT_POSITIONS,
        closed_gripper_joint_positions=pepper_robot.CLOSED_GRIPPER_JOINT_POSITIONS,
        max_effort=10.0,
        ignore_new_calls_while_executing=True,
        callback_group=callback_group,
        gripper_command_action_name="/LHand/gripper_command",
    )

    # Spin the node in background thread(s)
    executor = rclpy.executors.MultiThreadedExecutor(2)
    executor.add_node(node)
    executor_thread = Thread(target=executor.spin, daemon=True, args=())
    executor_thread.start()

    # Sleep a while in order to get the first joint state
    node.create_rate(10.0).sleep()

    # Get parameter
    action = node.get_parameter("action").get_parameter_value().string_value

    # Perform gripper action
    node.get_logger().info(f'Performing gripper action "{action}"')
    if "open" == action:
        moveit2_gripper.open()
        moveit2_gripper.wait_until_executed()
    elif "close" == action:
        moveit2_gripper.close()
        moveit2_gripper.wait_until_executed()
    else:
        period_s = 1.0
        rate = node.create_rate(1 / period_s)
        while rclpy.ok():
            moveit2_gripper()
            moveit2_gripper.wait_until_executed()
            rate.sleep()

    rclpy.shutdown()
    exit(0)


if __name__ == "__main__":
    main()
