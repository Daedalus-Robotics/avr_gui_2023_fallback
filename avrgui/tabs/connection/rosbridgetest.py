from __future__ import print_function
import roslibpy

client = roslibpy.Ros(host='100.94.194.90', port=9090)

client.run()

client.on_ready(lambda: print('Is ROS connected?', client.is_connected))

client.terminate()
