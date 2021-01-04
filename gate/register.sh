#!/bin/bash

set -e

if [ -z "$SSH_ORIGINAL_COMMAND" ]
then
	echo to register, please use the base64 encoded part of your ssh-ed25519 public key as command, for example:
	echo ssh -o StrictHostKeyChecking=no -p 2222 gate@fd66:666:$(cat /etc/team-num)::2 AAAAC3NzaC1lZDI1NTE5AAAAIGxJ1XYRi7wLu1olOC+hK7YPNvc/WSFQ2iNU+bkxsral
	exit 1
fi

set -u

U=user$(sha256sum <<< "$SSH_ORIGINAL_COMMAND" | cut -b 1-28)

SUDOC=/opt/bin/sudoc.py

$SUDOC useradd --create-home  --shell /bin/bash --password '*'  "$U" 
$SUDOC -u "$U" sh -e -c 'mkdir ~'$U'/.ssh; cat > ~'$U'/.ssh/authorized_keys' <<< "ssh-ed25519 $SSH_ORIGINAL_COMMAND"

echo now you can log in as user "$U"
