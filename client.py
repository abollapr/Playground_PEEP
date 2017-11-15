#Client

import asyncio
import playground
import random, logging
from .server import PEEPpacket
from playground.network.packet import PacketType
from playground.network.packet.fieldtypes import UINT32, STRING, UINT16, UINT8, BUFFER
from playground.network.packet.fieldtypes.attributes import Optional
from playground.network.common.Protocol import StackingProtocol, StackingProtocolFactory, StackingTransport
import zlib


class PeepClientTransport(StackingTransport):

    def __init__(self,protocol,transport):
        self.protocol = protocol
        self.transport = transport
        self.exc = None
        super().__init__(self.transport)


    def write(self, data):
        self.protocol.write(data)

    def close(self):
        self.protocol.close()

    def connection_lost(self):
        self.protocol.connection_lost(self.exc)

class PEEPClient(StackingProtocol):

    global_number_seq = 0
    global_number_ack = 0
    count_of_function_call = 0
    first_data_seq_number = 0
    count_of_function_call_ack = 0
    global_packet_size = 0
    number_of_packs = 0
    recv_window = {}
    prev_sequence_number = 0
    expected_ackno = 0
    sending_window = {}
    sending_window_count = 0
    global_pig = 0
    keylist1= []
    t = {}
    n = 0
    global_received_ack = 0
    prev_ack_number = 0
    backlog_window = []
    rip_received = 0
    ripack_received = 0
    RIP_PACKET = PEEPpacket()
    called_once = 0
    FLAG_CLOSE = 0

    def __init__(self, loop):
        self.transport = None
        self.loop = loop
        self._state = 0

    def calculateChecksum(self, c):
        self.c = c
        self.c.Checksum = 0
        checkbytes = self.c.__serialize__()
        return zlib.adler32(checkbytes) & 0xffff

    def checkChecksum(self, instance):
        self.instance = instance
        pullChecksum = self.instance.Checksum
        instance.Checksum = 0
        bytes = self.instance.__serialize__()
        if pullChecksum == zlib.adler32(bytes) & 0xffff :
            return True
        else:
            return False

    async def syn_timeout(self):
        while self._state < 2:
            await asyncio.sleep(1)
            if self._state < 2:
                self.transport.write(self.syn)

    async def ack_timeout(self):
        while self._state < 3:
            await asyncio.sleep(0.9)
            if self._state < 3:
                self.transport.write(self.clientpacketbytes)

    async def data_timeout(self):
        print("Server: Inside Data Timer")
        packets = list(self.t.values())
        while self.global_received_ack <= self.global_number_seq:
            await asyncio.sleep(0.1)
            for each_packet in packets:
                await asyncio.sleep(0.1)
                if self.global_received_ack <= self.global_number_seq:
                    if each_packet.packet.SequenceNumber == self.global_received_ack:
                        #each_packet.packet.Acknowledgement = self.global_number_ack
                        self.transport.write(each_packet.packet.__serialize__())
                        #each_packet.flag += 1
                        print("Server: Packet Retransmitted.", each_packet.packet.SequenceNumber)

    def connection_made(self, transport):
        print("=============== PEEP Client Connection_made CALLED =========\n")
        self.transport = transport
        self.protocol = self

        if self._state == 0:
            packet = PEEPpacket()
            packet.Type = 0
            packet.SequenceNumber = random.randrange(1, 1000, 1)
            packet.Acknowledgement = 0
            packet.Data = b"Piggy"
            self._state += 1
            print("Value of actual state is",self._state)
            print("=============== Sending SYN packet ==================\n")
            packet.Checksum = self.calculateChecksum(packet)
            self.syn = packet.__serialize__()
            self.transport.write(self.syn)
            self.ta = Timerx(0.1, self.syn_timeout, self.syn)

    def data_received(self, data):

        print("=============== PEEP Client Data_Received CALLED =============\n")
        self.deserializer = PEEPpacket.Deserializer()
        self.deserializer.update(data)
        for packet in self.deserializer.nextPackets():
            checkvalue = self.checkChecksum(packet)
            if self._state == 1 and packet.Type == 1:
                if checkvalue:
                    print("SYN-ACK Received. Seqno= ", packet.SequenceNumber, " Ackno=", packet.Acknowledgement)
                    self.ta.cancel()
                    #Sending ACK
                    if packet.Data == b"Piggy":
                       self.global_pig = 56
                       print(self.global_pig)
                       print("Choosing Piggybacking")
                    else:
                        print ("Choosing Selective")

                    ack = PEEPpacket()
                    ack.Type = 2
                    ack.SequenceNumber = packet.Acknowledgement
                    self.global_number_seq = ack.SequenceNumber
                    ack.Acknowledgement = packet.SequenceNumber + 1
                    if self.global_pig == 56:
                        ack.Data = b"Piggy"
                    self.global_number_ack = ack.Acknowledgement
                    self._state += 1
                    ack.Checksum = self.calculateChecksum(ack)
                    self.clientpacketbytes = ack.__serialize__()
                    print ("\n=================== Sending ACK =================\n")
                    self.transport.write(self.clientpacketbytes)
                    self.tb = Timerx(0.1, self.ack_timeout, self.clientpacketbytes)

                    peeptransport = PeepClientTransport(self, self.transport)
                    self.higherProtocol().connection_made(peeptransport)
                else:
                    print("Corrupt SYN-ACK packet received. Please check on server end.")


            elif packet.Type == 5:
                if checkvalue:
                    if self._state == 2:
                        self.tb.cancel()

                    print("====================Got Encapasulated Packet and Deserialized==================")
                    #print(packet.Data)
                    self._state +=1
                    #self.global_received_ack = packet.Acknowledgement
                    self.global_packet_size = len(packet.Data)
                    print("The size of packet is:", self.global_packet_size)
                    print("Seq number of incoming packet", packet.SequenceNumber)
                    print("Ack Number of incoming packet", packet.Acknowledgement)
                    self.receive_window(packet)
                else:
                    print("Corrupt Data packet received. Please check on server end.")

            elif packet.Type == 2:
                if checkvalue:
                    self.prev_ack_number = packet.Acknowledgement
                    self.pop_sending_window(packet.Acknowledgement)
                    print("ACK Received from the server. Removing data from buffer.", packet.Acknowledgement)
                    self.global_received_ack = packet.Acknowledgement

            elif packet.Type == 3:
                if checkvalue:
                    self.rip_received = 1
                    self.RIP_PACKET = packet
                    print("RIP Received from Server with Seq. No.:", packet.SequenceNumber,". Sending RIP-ACK")
                else:
                    print("Corrupt RIP packet received. Please check on server end.")

            elif packet.Type == 4:
                if checkvalue:
                    self.ripack_received = 1
                    self.pop_sending_window(packet.Acknowledgement)
                    print("RIP-ACK Received from Server. Closing down the connection.")
                else:
                    print("Corrupt RIP-ACK packet received. Please check on server end.")
            else:
                print("======== Incorrect packet received. Closing connection!=========\n")
                self.transport.close()

    def sendack(self, ackno):
        print ("================== Sending ACK ================\n")

        ack = PEEPpacket()
        calcChecksum = PEEPClient(self.loop)
        ack.Type = 2
        ack.Acknowledgement = ackno
        print ("ACK No:" + str(ack.Acknowledgement))
        # For debugging
        ack.Checksum = calcChecksum.calculateChecksum(ack)
        print(ack.Checksum)
        bytes = ack.__serialize__()
        self.transport.write(bytes)


    def write(self,data):
        print ("=================== Writing Data down to wire from Client ================\n")
        self.i = 0
        self.l = 1
        udata = data
        while self.i < len(udata):
            chunk, data = data[:1024], data[1024:]
            self.backlog_window.append(chunk)
            self.i += 1024
            self.l += 1
            if self.sending_window_count <= 100:
                if self.backlog_window != []:
                    print("About to pop backlog in client")
                    data_from_BL = self.backlog_window.pop(0)
                    self.encapsulating_packet(data_from_BL)

    def encapsulating_packet(self,data_from_BL_1):
        chunk = data_from_BL_1
        if chunk == b'rip':
            if self.called_once == 0:
                self.called_once = 1
                self.rip = PEEPpacket()
                self.rip.Type = 3
                self.rip.Acknowledgement = self.global_number_ack
                self.rip.SequenceNumber = self.update_sequence(chunk)
                calcChecksum = PEEPClient(self.loop)
                self.rip.Checksum = calcChecksum.calculateChecksum(self.rip)
                self.update_sending_window(self.rip)
                ripbites = self.rip.__serialize__() # :P
                print(" Writing down RIP Packet to wire after updating window ")
                self.transport.write(ripbites)
                self.tz = Timerx(0.1, self.connection_timeout, self.rip)
                self.chabi = self.rip.SequenceNumber
                self.t[self.chabi] = self.tz
            else:
                self.rip = PEEPpacket()
                self.rip.Type = 3
                self.rip.Acknowledgement = self.global_number_ack
                self.rip.SequenceNumber = self.update_sequence(chunk)
                print("RIP SEQ number and ACK number is",self.rip.SequenceNumber,self.rip.Acknowledgement)
                calcChecksum = PEEPClient(self.loop)
                self.rip.Checksum = calcChecksum.calculateChecksum(self.rip)
                ripbites = self.rip.__serialize__()  # :P
                print(" REEEEWriting down RIP Packet to wire after updating window ")
                self.transport.write(ripbites)
                (self.t[self.chabi]).cancel()
                self.t.pop(self.chabi)
                self.tz = Timerx(0.1, self.connection_timeout, self.rip)
                self.chabi = self.rip.SequenceNumber
                self.t[self.chabi] = self.tz

        else:
            self.Cencap = PEEPpacket()
            #self.n += 1
            calcChecksum = PEEPClient(self.loop)
            self.Cencap.Type = 5
            self.Cencap.SequenceNumber = self.update_sequence(chunk)
            self.prev_sequence_number = self.Cencap.SequenceNumber  # prev_sequence_number is the seq number of the packet sent by client
            print("SEQ No:" + str(self.Cencap.SequenceNumber))
            self.Cencap.Acknowledgement = self.global_number_ack  #
            print("ACK No:" + str(self.Cencap.Acknowledgement))
            self.Cencap.Data = chunk
            # print ("Data is", chunk)
            print("Size of data", len(chunk))
            self.Cencap.Checksum = calcChecksum.calculateChecksum(self.Cencap)
            self.Cencap = self.update_sending_window(self.Cencap)
            self.bytes = self.Cencap.__serialize__()
            self.transport.write(self.bytes)
            # Creating timer for each data packet
            self.timer = PEEPClient(loop)
            self.tx = Timerx(0.1, self.data_timeout, self.Cencap)
            self.chabi = self.global_number_seq
            self.t[self.chabi] = self.tx

    def receive_window(self, pkt):
        self.number_of_packs += 1
        self.packet = pkt
        if self.packet.SequenceNumber == self.global_number_ack:
            self.global_number_ack = self.update_ack(self.packet.SequenceNumber, self.global_packet_size)  #It's actually updating the expected Seq Number
            print("Client global number ack",self.global_number_ack)
            self.sendack(self.update_ack(self.packet.SequenceNumber, self.global_packet_size))
            self.higherProtocol().data_received(self.packet.Data)
            self.check_receive_window()

        elif self.number_of_packs <= 1000:
            #and self.packet.SequenceNumber <= self.global_number_ack + (1024*1000):
            self.recv_window[self.packet.SequenceNumber] = self.packet.Data
            self.sendack(self.global_number_ack)
            #self.check_receive_window()

        else:
            print ("Receive window is full or the packet has already been received!")

    def check_receive_window(self):
        sorted_list = []
        sorted_list = self.recv_window.keys()

        for k in sorted_list:
            if k == self.global_number_ack:
                self.packet_to_be_popped = self.recv_window[k]
                self.sendack(self.update_ack(self.packet_to_be_popped.SequenceNumber, self.global_packet_size))
                self.higherProtocol().data_received(self.packet_to_be_popped.Data)
            else:
                return


    prev_packet_size = 0

    def calculate_length(self, data):
        self.prev_packet_size = len(data)


    def update_sequence(self, data):
        if self.count_of_function_call == 0:
            self.count_of_function_call = 1
            self.calculate_length(data)
            return self.global_number_seq #for first packet this is equal to synack.ackno
        else:
            self.global_number_seq = self.prev_sequence_number + self.prev_packet_size
            self.calculate_length(data)
            return self.global_number_seq

    def update_ack(self, received_seq_number, size):
        self.received_seq_number = received_seq_number
        self.global_number_ack = self.received_seq_number + size
        return self.global_number_ack

    def update_sending_window(self, packet):
        self.packet = packet
        self.sending_window_count += 1
        self.key = self.global_number_seq
        self.sending_window[self.key] = self.packet
        keylist = self.sending_window.keys()
        self.keylist1 = sorted(keylist)
        return self.packet

    def pop_sending_window(self, AckNum):
        print ("Client sending window count",self.sending_window_count)
        self.AckNum = AckNum
        for key in self.keylist1:
            #print ("Key is: ", key)
            if (self.AckNum > key):
                print ("#Client Window#:",self.keylist1)
                print("Key value to pop is", key)
                seqs = list(self.t.keys())
                for chabi in seqs:
                    if self.AckNum > chabi:
                        (self.t[chabi]).cancel()
                        self.t.pop(chabi)
                self.sending_window.pop(key)
                self.keylist1.pop(0)
                self.sending_window_count = self.sending_window_count - 1
                print("client: sending window count is", self.sending_window_count)
                if self.sending_window_count <= 100:
                    print("About to pop backlog")
                    if self.backlog_window != []:
                        data_from_BL = self.backlog_window.pop(0)
                        self.encapsulating_packet(data_from_BL)
                    if self.sending_window_count == 0: #and self.FLAG_CLOSE == 1:
                        print ("Client: About to SEND RIP!!!!")
                        Data = b'rip'
                        self.write(Data)

        if self.sending_window_count == 0 and self.FLAG_CLOSE == 1:
            Data = b'rip'
            self.write(Data)

        if self.sending_window_count == 0 and self.ripack_received==1 and self.backlog_window == []:
            print ("Recieved RIP ACK.. Closing client connection")
            self.close_timers()
            self._state += 1
            self.connection_lost()


        return


    def close_timers(self):
        for k,v in self.t.items():
            print("cancelling timers.")
            v.cancel()

    def close(self):
        self.FLAG_CLOSE = 1



    def connection_lost(self,exc):
        print ("============== PEEPClient Closing connection ===========\n")
        self.transport.close()
        self.loop.stop()

    async def connection_timeout(self):
        while self.sending_window_count >= 0:
            await asyncio.sleep(0.2)
            if len(self.keylist1) < 2:
                await asyncio.sleep(0.2)
                Data = b'rip'
                self.write(Data)
                #self.connection_lost(self)

    #Timer Function code block starts here
    #Timer Function code block starts here
class Timerx():

    def __init__(self, timeout, callback, packet):
        self._timeout = timeout
        self._callback = callback
        self.packet = packet
        self.flag = 0
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
            self._task.cancel()


loop = asyncio.get_event_loop()

    #logging.getLogger().setLevel(logging.NOTSET)  # this logs *everything*
    #logging.getLogger().addHandler(logging.StreamHandler())  # logs to stderr

Clientfactory = StackingProtocolFactory(lambda: PEEPClient(loop))

'''if __name__ == "__main__":

    loop = asyncio.get_event_loop()

    logging.getLogger().setLevel(logging.NOTSET)  # this logs *everything*
    logging.getLogger().addHandler(logging.StreamHandler())  # logs to stderr

    Clientfactory = StackingProtocolFactory(lambda: PEEPClient(loop))
    ptConnector = playground.Connector(protocolStack=Clientfactory)

    playground.setConnector("passthrough", ptConnector)

    go = initiate(loop)
    coro = playground.getConnector('passthrough').create_playground_connection(go.send_first_packet, '20174.1.1.1', 8888)
    loop.run_until_complete(coro)

    loop.run_forever()
    loop.close()'''
