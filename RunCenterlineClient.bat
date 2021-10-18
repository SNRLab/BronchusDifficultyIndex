REM bat file for Windows OS

@echo off
echo %1
echo %2
echo "Entered batch file..."
echo "Starting client server with port number: %1"
echo "Opening client script via command: %2"
python %2 %1
pause