---
description: Send a cc-chat message to a contact
argument-hint: <alias> <message>
allowed-tools: Bash(chat send *)
---

Send a cc-chat message. Arguments: $ARGUMENTS

The first word is the recipient's alias; everything after it is the message body.
Run `chat send <alias> "<message>"` (quote the body correctly), then tell me
whether it was sent or queued for later delivery.
