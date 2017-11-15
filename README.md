# Playground_PEEP

PEEP protocol is a reliable transport layer that sits in the PLAYGROUND model of networking. The lowest layer of the playground model is the wire protocol. The PEEP protocol sits right above the wire protocol layer.  The PEEP protocol takes data from the above layer and sends them over an negotiated session between the two ends. Every entitiy running the PEEP protocol must maintain a PEEP address and a port number. The PEEP address and the port number together are used by the other end's PEEP protocol is used to connect and send data. PEEP works by encapsulating the data that it receives from the higher layer and adding meta data onto it that helps in keeping track of the packet that is both transmitted and received. PEEP ensure reliable data transmission by maintaining a sequence number and a acknowledgment number.

Read through the PEEP_RFC for more information.
