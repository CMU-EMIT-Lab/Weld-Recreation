import os
from dotenv import load_dotenv
import socket

# initialize variables
load_dotenv()
robotIP = os.getenv("ROBOT-IP")
if not robotIP:
    raise ValueError("ROBOT-IP is not set in the environment or .env file")
PRIMARY_PORT = 30001
SECONDARY_PORT = 30002
REALTIME_PORT = 30003

# URScript command being sent to the robot
# urscript_command = "set_digital_out(1, True)"
urscript_command = "movel(p[0.400000, 0.000000, 0.010000, 3.141593, 0.000000, 0.000000], a=0.3000, v=0.0200, r=0.0020)"
# urscript_command = "movel(p[0.2, 0.4, 0.3, 0, 3.14, 0], a=1.2, v=0.25)"

# Creates new line
new_line = "\n"

def send_urscript_command(command: str):
    """
    This function takes the URScript command defined above, 
    connects to the robot server, and sends 
    the command to the specified port to be executed by the robot.

    Args:
        command (str): URScript command
        
    Returns: 
        None
    """
    try:
        # Create a socket connection with the robot IP and port number defined above
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((robotIP, SECONDARY_PORT))

        # Appends new line to the URScript command (the command will not execute without this)
        command = command + new_line
        
        # Send the command
        s.sendall(command.encode('utf-8'))
        
        # Close the connection
        s.close()

    except Exception as e:
        print(f"An error occurred: {e}")

def send_script_file(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            send_urscript_command(file.read())
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return

send_script_file("codegen/demo_gcode/box_weld.script")