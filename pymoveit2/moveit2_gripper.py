import math
from typing import List, Optional

from rclpy.callback_groups import CallbackGroup
from rclpy.node import Node

from .moveit2 import *


class MoveIt2Gripper(MoveIt2):
    """
    Python interface for MoveIt 2 Gripper that is controlled by JointTrajectoryController.
    This implementation builds on MoveIt2 to reuse code (while keeping MoveIt2 standalone).
    """

    def __init__(
        self,
        node: Node,
        gripper_joint_names: List[str],
        open_gripper_joint_positions: List[float],
        closed_gripper_joint_positions: List[float],
        gripper_group_name: str = "LHand",
        execute_via_moveit: bool = False,
        ignore_new_calls_while_executing: bool = False,
        skip_planning: bool = False,
        skip_planning_fixed_motion_duration: float = 0.5,
        callback_group: Optional[CallbackGroup] = None,
        follow_joint_trajectory_action_name: str = "gripper_trajectory_controller/follow_joint_trajectory",
    ):
        # Validation of inputs
        if len(gripper_joint_names) != len(open_gripper_joint_positions) or len(gripper_joint_names) != len(closed_gripper_joint_positions):
            raise ValueError("The length of gripper_joint_names must match the lengths of both open_gripper_joint_positions and closed_gripper_joint_positions.")

        super().__init__(
            node=node,
            joint_names=gripper_joint_names,
            base_link_name="",
            end_effector_name="",
            group_name=gripper_group_name,
            execute_via_moveit=execute_via_moveit,
            ignore_new_calls_while_executing=ignore_new_calls_while_executing,
            callback_group=callback_group,
            follow_joint_trajectory_action_name=follow_joint_trajectory_action_name,
        )
        self.__del_redundant_attributes()

        self.__open_gripper_joint_positions = open_gripper_joint_positions
        self.__closed_gripper_joint_positions = closed_gripper_joint_positions

        self.__skip_planning = skip_planning
        if skip_planning:
            duration_sec = math.floor(skip_planning_fixed_motion_duration)
            duration_nanosec = int(
                10e8 * (skip_planning_fixed_motion_duration - duration_sec)
            )
            self.__open_dummy_trajectory_goal = init_follow_joint_trajectory_goal(
                init_dummy_joint_trajectory_from_state(
                    init_joint_state(
                        joint_names=gripper_joint_names,
                        joint_positions=open_gripper_joint_positions,
                    ),
                    duration_sec=duration_sec,
                    duration_nanosec=duration_nanosec,
                )
            )
            self.__close_dummy_trajectory_goal = init_follow_joint_trajectory_goal(
                init_dummy_joint_trajectory_from_state(
                    init_joint_state(
                        joint_names=gripper_joint_names,
                        joint_positions=closed_gripper_joint_positions,
                    ),
                    duration_sec=duration_sec,
                    duration_nanosec=duration_nanosec,
                )
            )

        # Tolerance for open/close position checks
        self.__open_tolerance = [
            0.1 * abs(o - c) for o, c in zip(open_gripper_joint_positions, closed_gripper_joint_positions)
        ]
        self.__gripper_joint_indices: Optional[List[int]] = None


    def __call__(self):
        """
        Callable that is identical to `MoveIt2Gripper.toggle()`.
        """

        self.toggle()

    def toggle(self):
        """
        Toggles the gripper between open and closed state.
        """

        if self.is_open:
            self.close(skip_if_noop=False)
        else:
            self.open(skip_if_noop=False)

    def open(self, skip_if_noop: bool = True):
        """
        Open the gripper.
        - `skip_if_noop` - No action will be performed if the gripper is already open.
        """

        if skip_if_noop and self.is_open:
            return

        if self.__skip_planning:
            self.__open_without_planning()
        else:
            self.move_to_configuration(
                joint_positions=self.__open_gripper_joint_positions
            )

    def close(self, skip_if_noop: bool = True):
        """
        Close the gripper.
        - `skip_if_noop` - No action will be performed if the gripper is not open.
        """

        if skip_if_noop and self.is_closed:
            return

        if self.__skip_planning:
            self.__close_without_planning()
        else:
            self.move_to_configuration(
                joint_positions=self.__closed_gripper_joint_positions
            )

    def reset_open(self, sync: bool = True):
        """
        Reset into open configuration by sending a dummy joint trajectory.
        This is useful for simulated robots that allow instantaneous reset of joints.
        """

        self.reset_controller(
            joint_state=self.__open_gripper_joint_positions, sync=sync
        )

    def reset_closed(self, sync: bool = True):
        """
        Reset into closed configuration by sending a dummy joint trajectory.
        This is useful for simulated robots that allow instantaneous reset of joints.
        """

        self.reset_controller(
            joint_state=self.__closed_gripper_joint_positions, sync=sync
        )

    def __open_without_planning(self):

        self._send_goal_async_follow_joint_trajectory(
            goal=self.__open_dummy_trajectory_goal,
            wait_until_response=False,
        )

    def __close_without_planning(self):

        self._send_goal_async_follow_joint_trajectory(
            goal=self.__close_dummy_trajectory_goal,
            wait_until_response=False,
        )

    def __del_redundant_attributes(self):

        self.move_to_pose = None
        self.set_pose_goal = None
        self.set_position_goal = None
        self.set_orientation_goal = None
        self.compute_fk = None
        self.compute_ik = None

    @property
    def is_open(self) -> bool:
        """
        Gripper is considered to be open if all of the joints are at their open position.
        """

        joint_state = self.joint_state

        # Assume the gripper is open if there are no joint state readings yet
        if joint_state is None:
            return True

        # For the sake of performance, find the indices of joints only once.
        # This is especially useful for robots with many joints.
        if self.__gripper_joint_indices is None:
            self.__gripper_joint_indices: List[int] = []
            for joint_name in self.joint_names:
                self.__gripper_joint_indices.append(joint_state.name.index(joint_name))

        for local_joint_index, joint_state_index in enumerate(
            self.__gripper_joint_indices
        ):
            if (
                abs(
                    joint_state.position[joint_state_index]
                    - self.__open_gripper_joint_positions[local_joint_index]
                )
                > self.__open_tolerance[local_joint_index]
            ):
                return False

        return True

    @property
    def is_closed(self) -> bool:
        """
        Gripper is considered to be closed if any of the joints is outside of their open position.
        """

        return not self.is_open
