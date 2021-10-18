#!/bin/bash

echo "Entered bash file..."
echo "Starting client server with port number: $1"
echo "Opening client script via command: $2"
/usr/bin/python3 $2 $1
exit