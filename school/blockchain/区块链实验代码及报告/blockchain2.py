import time
import json
import threading
from hashlib import sha256
from datetime import datetime
from random import choice
from queue import Queue, Empty

from socketserver import BaseRequestHandler, ThreadingTCPServer

# 需要两个队列
# 定义变量
block_chain = []
temp_blocks = []
candidate_blocks = Queue()  # 创建队列，用于线程间通信
announcements = Queue()
validators = {}

My_Lock = threading.Lock()


def generate_block(oldblock, bpm, address):
    """
    :param oldblock:
    :param bpm:
    :param address:
    :return:
    """
    newblock = {
        "Index": oldblock["Index"] + 1,
        "BPM": bpm,
        "Timestamp": str(datetime.now()),
        "PrevHash": oldblock["Hash"],
        "Validator": address
    }

    newblock["Hash"] = calculate_hash(newblock)
    return newblock


def calculate_hash(block):
    record = "".join([
        str(block["Index"]),
        str(block["BPM"]),
        block["Timestamp"],
        block["PrevHash"]
    ])

    return sha256(record.encode()).hexdigest()


def is_block_valid(newblock, oldblock):
    """
    :param newblock:
    :param oldblock:
    :return:
    """

    if oldblock["Index"] + 1 != newblock["Index"]:
        return False

    if oldblock["Hash"] != newblock["PrevHash"]:
        return False

    if calculate_hash(newblock) != newblock["Hash"]:
        return False

    return True


def pick_winner(announcements):
    """
    选择记账人
    :param announcements:
    :return:
    """
    time.sleep(10)

    while True:
        with My_Lock:
            temp = temp_blocks

        lottery_pool = []  #

        if temp:
            for block in temp:
                if block["Validator"] not in lottery_pool:
                    set_validators = validators
                    k = set_validators.get(block["Validator"])
                    if k:
                        lottery_pool.append(block["Validator"] for _ in k)

            lottery_winner = choice(lottery_pool)

            # 向区块链添加赢家区块，并让所有其他节点都知道
            for block in temp:
                if block["Validator"] == lottery_winner:
                    with My_Lock:
                        block_chain.append(block)

                    # 在队列中写入消息

                    for _ in range(len(validators)):
                        msg = "\n:{0} 赢得了记账权利\n".format(lottery_winner)
                        announcements.put(msg)

                    break

        with My_Lock:
            temp_blocks.clear()


class HandleConn(BaseRequestHandler):
    def handle(self):
        print("Got connection from", self.client_address)
        while True:

            # todo线程始终将信息同步到客户端
            try:
                msg = announcements.get(block=False)
                self.request.send(msg.encode())
            except Empty:
                pass

            #验证程序地址
            self.request.send(b"Enter token balance:")
            balance = self.request.recv(8192)

            try:
                balance = int(balance)
            except Exception as e:
                print(e)
                break

            t = str(datetime.now())
            address = sha256(t.encode()).hexdigest()
            validators[address] = balance
            print(validators)

            self.request.send(b"\nEnter a new BPM:")
            bpm = self.request.recv(8192)
            # todo线程生成新块
            try:
                bpm = int(bpm)
            except Exception as e:
                print(e)
                del validators[address]
                break

            last_block = block_chain[-1]

            new_block = generate_block(last_block, bpm, address)

            print(new_block, last_block)
            if is_block_valid(new_block, last_block):
                candidate_blocks.put(new_block)

            self.request.send(b"\nEnter a new BPM:")

            # todo线程总是向客户端发送消息
            time.sleep(30)
            with My_Lock:
                output = json.dumps(block_chain)

            self.request.send(output.encode())


def candidate(candidate_blocks):
    while True:
        try:
            candi = candidate_blocks.get(block=False)
        except Empty:
            time.sleep(3)
            continue
        temp_blocks.append(candi)


def run():
    # 创建一个genesis块
    t = str(datetime.now())
    genesis_block = {
        "Index": 0,
        "Timestamp": t,
        "BPM": 0,
        "PrevHash": "",
        "Validator": ""
    }

    genesis_block["Hash"] = calculate_hash(genesis_block)
    print(genesis_block)
    block_chain.append(genesis_block)

    # 开始一个tcp服务
    serv = ThreadingTCPServer(('', 9090), HandleConn)
    serv.serve_forever()

    thread_canditate = threading.Thread(target=candidate, args=(candidate_blocks,))
    thread_pick = threading.Thread(target=pick_winner, args=(announcements,))

    thread_canditate.start()
    thread_pick.start()


if __name__ == '__main__':
    run()
