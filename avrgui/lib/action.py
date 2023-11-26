import json
from typing import Any, Callable

import roslibpy
from roslibpy import Ros


class Action:
    def __init__(self,
                 ros: Ros,
                 action_id: int,
                 feedback_callback: Callable[[dict[str, Any]], None],
                 result_callback: Callable[[dict[str, Any]], None]) -> None:
        self.ros = ros
        self.id = action_id
        self._feedback_callback = feedback_callback
        self._result_callback = result_callback

        self.goal_client = roslibpy.Service(
            self.ros,
            '/action_bridge/goal',
            'avr_vmc_2023_action_bridge_interfaces/srv/Goal'
        )
        self.cancel_client = roslibpy.Service(
            self.ros,
            '/action_bridge/cancel',
            'avr_vmc_2023_action_bridge_interfaces/srv/Cancel'
        )

        self.feedback_subscriber = roslibpy.Topic(
            self.ros,
            '/action_bridge/feedback',
            'avr_vmc_2023_action_bridge_interfaces/msg/Feedback'
        )
        self.result_subscriber = roslibpy.Topic(
            self.ros,
            '/action_bridge/result',
            'avr_vmc_2023_action_bridge_interfaces/msg/Result'
        )

        self.feedback_subscriber.subscribe(self._feedback)
        self.result_subscriber.subscribe(self._result)

        self.running = False

    def send_goal(self, goal_data: dict[str, Any]) -> None:
        if not self.running:
            data = json.dumps(goal_data)
            goal = roslibpy.ServiceRequest({'id': self.id, 'data': data})
            self.goal_client.call(
                goal,
                lambda msg: print(f'Sent goal for id: {self.id}')
            )
            self.running = True

    def cancel(self) -> None:
        if self.running:
            cancel = roslibpy.ServiceRequest({'id': self.id})
            self.cancel_client.call(
                cancel,
                lambda msg: print(f'Sent cancel request for id: {self.id}')
            )
        self.running = False

    def _feedback(self, msg: Any) -> None:
        if msg['id'] == self.id:
            try:
                data = json.loads(msg['data'])
            except json.JSONDecodeError:
                print(f'Failed to decode json for feedback on id: {self.id}')
            else:
                if self.running:
                    self._feedback_callback(data)

    def _result(self, msg: Any) -> None:
        self.running = False
        if msg['id'] == self.id:
            try:
                data = json.loads(msg['data'])
            except json.JSONDecodeError:
                print(f'Failed to decode json for result on id: {self.id}')
            else:
                if self.running:
                    self._result_callback(data)
