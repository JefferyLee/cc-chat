---
description: Send a toxi message to a contact
argument-hint: <alias> <message>
allowed-tools: Bash(toxi send *)
---

Send a toxi message. Arguments: $ARGUMENTS

The first word is the recipient's alias; everything after it is the message body.
Run `toxi send <alias> "<message>"` (quote the body correctly), then tell me
whether it was sent or queued for later delivery.
