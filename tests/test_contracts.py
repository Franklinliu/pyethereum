import os
import pytest
from pyethereum import tester
import logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')
logger = logging.getLogger()

# customize VM log output to your needs
# hint: use 'py.test' with the '-s' option to dump logs to the console
pblogger = tester.pb.pblogger
pblogger.log_pre_state = True    # dump storage at account before execution
pblogger.log_post_state = True   # dump storage at account after execution
pblogger.log_block = False       # dump block after TX was applied
pblogger.log_memory = False      # dump memory before each op
pblogger.log_op = True           # log op, gas, stack before each op
pblogger.log_json = False        # generate machine readable output

gasprice = 0
startgas = 10000

sixten_code =\
    '''
(with 'x 10
    (with 'y 20
        (with 'z 30
            (seq
                (set 'a (add (mul (get 'y) (get 'z)) (get 'x)))
                (return (ref 'a) 32)
            )
        )
    )
)
'''


def test_sixten():
    s = tester.state()
    c = s.contract('')
    s.block.set_code(c, tester.serpent.compile_lll(sixten_code))
    o1 = s.send(tester.k0, c, 0, [])
    assert o1 == [610]

mul2_code = \
    '''
return(msg.data[0]*2)
'''

filename = "mul2_qwertyuioplkjhgfdsa.se"

returnten_code = \
    '''
x = create("%s")
return(call(x, 5))
''' % filename


def test_returnten():
    s = tester.state()
    open(filename, 'w').write(mul2_code)
    c = s.contract(returnten_code)
    o1 = s.send(tester.k0, c, 0, [])
    os.remove(filename)
    assert o1 == [10]

namecoin_code =\
    '''
if !contract.storage[msg.data[0]]:
    contract.storage[msg.data[0]] = msg.data[1]
    return(1)
else:
    return(0)
'''


def test_namecoin():
    s = tester.state()
    c = s.contract(namecoin_code)
    o1 = s.send(tester.k0, c, 0, ['"george"', 45])
    assert o1 == [1]
    o2 = s.send(tester.k0, c, 0, ['"george"', 20])
    assert o2 == [0]
    o3 = s.send(tester.k0, c, 0, ['"harry"', 60])
    assert o3 == [1]

    assert s.block.to_dict()


currency_code = '''
init:
    contract.storage[msg.sender] = 1000
code:
    if msg.datasize == 1:
        addr = msg.data[0]
        return(contract.storage[addr])
    else:
        from = msg.sender
        fromvalue = contract.storage[from]
        to = msg.data[0]
        value = msg.data[1]
        if fromvalue >= value:
            contract.storage[from] = fromvalue - value
            contract.storage[to] = contract.storage[to] + value
            return(1)
        else:
            return(0)
'''


def test_currency():
    s = tester.state()
    c = s.contract(currency_code, sender=tester.k0)
    o1 = s.send(tester.k0, c, 0, [tester.a2, 200])
    assert o1 == [1]
    o2 = s.send(tester.k0, c, 0, [tester.a2, 900])
    assert o2 == [0]
    o3 = s.send(tester.k0, c, 0, [tester.a0])
    assert o3 == [800]
    o4 = s.send(tester.k0, c, 0, [tester.a2])
    assert o4 == [200]


data_feed_code = '''
if !contract.storage[1000]:
    contract.storage[1000] = 1
    contract.storage[1001] = msg.sender
    return(20)
elif msg.datasize == 2:
    if msg.sender == contract.storage[1001]:
        contract.storage[msg.data[0]] = msg.data[1]
        return(1)
    else:
        return(0)
else:
    return(contract.storage[msg.data[0]])
'''


def test_data_feeds():
    s = tester.state()
    c = s.contract(data_feed_code, sender=tester.k0)
    o1 = s.send(tester.k0, c, 0)
    assert o1 == [20]
    o2 = s.send(tester.k0, c, 0, [500])
    assert o2 == [0]
    o3 = s.send(tester.k0, c, 0, [500, 19])
    assert o3 == [1]
    o4 = s.send(tester.k0, c, 0, [500])
    assert o4 == [19]
    o5 = s.send(tester.k1, c, 0, [500, 726])
    assert o5 == [0]
    o6 = s.send(tester.k0, c, 0, [500, 726])
    assert o6 == [1]
    return s, c

hedge_code = '''
if !contract.storage[1000]:
    contract.storage[1000] = msg.sender
    contract.storage[1002] = msg.value
    contract.storage[1003] = msg.data[0]
    contract.storage[1004] = msg.data[1]
    return(1)
elif !contract.storage[1001]:
    ethvalue = contract.storage[1002]
    if msg.value >= ethvalue:
        contract.storage[1001] = msg.sender
    c = call(contract.storage[1003],[contract.storage[1004]],1)
    othervalue = ethvalue * c
    contract.storage[1005] = othervalue
    contract.storage[1006] = block.timestamp + 500
    return([2,othervalue],2)
else:
    othervalue = contract.storage[1005]
    ethvalue = othervalue / call(contract.storage[1003],contract.storage[1004])
    if ethvalue >= contract.balance:
        send(contract.storage[1000],contract.balance)
        return(3)
    elif block.timestamp > contract.storage[1006]:
        send(contract.storage[1001],contract.balance - ethvalue)
        send(contract.storage[1000],ethvalue)
        return(4)
    else:
        return(5)
'''


def test_hedge():
    s, c = test_data_feeds()
    c2 = s.contract(hedge_code, sender=tester.k0)
    o1 = s.send(tester.k0, c2, 10**16, [c, 500])
    assert o1 == [1]
    o2 = s.send(tester.k2, c2, 10**16)
    assert o2 == [2, 7260000000000000000]
    snapshot = s.snapshot()
    o3 = s.send(tester.k0, c, 0, [500, 300])
    assert o3 == [1]
    o4 = s.send(tester.k0, c2, 0)
    assert o4 == [3]
    s.revert(snapshot)
    o5 = s.send(tester.k0, c2, 0)
    assert o5 == [5]
    s.mine(10, tester.a3)
    o6 = s.send(tester.k0, c2, 0)
    assert o6 == [4]


arither_code = '''
init:
    contract.storage[0] = 10
code:
    if msg.data[0] == 0:
        contract.storage[0] += 1
    elif msg.data[0] == 1:
        contract.storage[0] *= 10
        call(contract.address, 0)
        contract.storage[0] *= 10
    elif msg.data[0] == 2:
        contract.storage[0] *= 10
        postcall(tx.gas / 2, contract.address, 0)
        contract.storage[0] *= 10
    elif msg.data[0] == 3:
        return(contract.storage[0])
'''
 

def test_post():
    s = tester.state()
    c = s.contract(arither_code)
    s.send(tester.k0, c, 0, [1])
    o2 = s.send(tester.k0, c, 0, [3])
    assert o2 == [1010]
    c = s.contract(arither_code)
    s.send(tester.k0, c, 0, [2])
    o2 = s.send(tester.k0, c, 0, [3])
    assert o2 == [1001]


suicider_code = '''
if msg.data[0] == 0:
    call(contract.address, 3)
    i = 0
    while i < msg.data[1]:
        i += 1
elif msg.data[0] == 1:
    msg(tx.gas - 100, contract.address, 0, [0, msg.data[1]], 2)
elif msg.data[0] == 2:
    return(10)
elif msg.data[0] == 3:
    suicide(0)
'''


def test_suicider():
    s = tester.state()
    c = s.contract(suicider_code)
    tester.gas_limit = 4000
    s.send(tester.k0, c, 0, [1, 10])
    o2 = s.send(tester.k0, c, 0, [2])
    assert o2 == []
    c = s.contract(suicider_code)
    s.send(tester.k0, c, 0, [1, 4000])
    o2 = s.send(tester.k0, c, 0, [2])
    assert o2 == [10]

test_suicider()
