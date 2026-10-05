#!/bin/sh
# Container action entrypoint: greet, report the OS and user, write an output.
. /etc/os-release
echo "REPORT docker_action greeting=hello,_$1 os=$ID uid=$(id -u)"
echo "result=ok" >> "$GITHUB_OUTPUT"
