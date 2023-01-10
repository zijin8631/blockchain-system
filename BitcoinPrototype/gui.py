import PySimpleGUI as sg
import cli
from block_chain import BlockChain
from xmlrpc.client import ServerProxy
import subprocess

# sg.theme('DarkAmber')   # 设置当前主题

"""Initialization"""
bc = BlockChain()
s = ServerProxy("http://localhost:9999")
parser = cli.new_parser()
args = parser.parse_args()
"""Structure"""


# 界面布局，将会按照列表顺序从上往下依次排列，二级列表中，从左往右依此排列
status_string = "here display connect status" # connect status
wallet_address = 'here display wallet address'
wallets_list = ["Click the button and show your address"]
balance_in_address = "display the balance in previous address"
chain_details = "display Chain Details"
initial_balance_text = "Please input a address or select one from the list"
transactionStatus = 'Your transaction status'

layout = [
    [sg.Button('1.Create Address',size=(15,1)), sg.InputText('Your new address',size=(40,1),key=wallet_address),
    sg.Button('2.Print Wallet',size=(15,1)), sg.InputCombo(size=(40,5),values=wallets_list, key='walletlist')],
    [sg.Button('3.Check Balance',size=(15,1)), sg.InputText(initial_balance_text, size=(40,1), key='balanceText',enable_events=True),
    sg.Text(balance_in_address, key="balanceAddress")],
    [sg.Text("---------------------------------------------------------------------------------------------------------"
             "-----------------------------------------------------------------------")],
    [sg.Button('4.Transaction',size=(15,1))],
    [sg.InputText('Sender',size=(40,1),key='sendAddr'),sg.InputText('Receiver',size=(40,1),key='recAddr'),
                        sg.InputText('Amount',size=(20,1),key='amount')],
    [sg.Text(transactionStatus, key="txstatus")],
    [sg.Text("----------------------------------------------------------------------------------------------------------"
             "----------------------------------------------------------------------")],
    [sg.Button('5.Print Chain',size=(15,1)), sg.Multiline(chain_details,size=(100,4),key=chain_details)],
    [sg.Button('Mine a Genesis Block(Only Press Once!)'), sg.Button('Synchronize'),sg.Button('Quit')]
]
layout2 = []

# 创造窗口
window = sg.Window('฿-Simple Bitcoin System-฿', layout)
# 事件循环并获取输入值
while True:
    client = cli.Cli()
    event, values = window.read()

    if event in (None, 'Quit'):   # 如果用户关闭窗口或点击`Cancel`
        break
    if event == 'Synchronize':
        cmd_string = 'python cli.py start'
        subprocess.run(cmd_string, shell=True)

    if event == 'Mine a Genesis Block(Only Press Once!)':
        Gaddr = client.create_genesis_block()
        window[wallet_address].update(Gaddr)
    if event == '1.Create Address':
        try:
            new_address = client.create_wallet()
        except:
            new_address = "Error occurred in Creating Wallet!"
        window[wallet_address].update(new_address)

    if event == '2.Print Wallet':
        new_wallet_list = client.print_all_wallet()
        window['walletlist'].update(values=new_wallet_list, set_to_index=0)

    if event == '3.Check Balance':
        selected_address = ''
        balance = 0
        if values['balanceText'] != '' and values['balanceText'] != initial_balance_text:
            selected_address = values['balanceText']
            balance = client.get_balance(selected_address)
        elif values['walletlist'] != "" and values['walletlist'] != wallets_list[0]:
            selected_address = values['walletlist']
            balance = client.get_balance(selected_address)
        else:
            tempstring = 'Invalid input!'
            window["balanceAddress"].update(tempstring)
            continue
        balance_str = ('%s balance is %d' % (selected_address, balance))
        window["balanceAddress"].update(balance_str)

    if event == '4.Transaction':
        try:
            print(values['sendAddr'],values['recAddr'],values['amount'])
            response = client.send(values['sendAddr'],values['recAddr'],int(values['amount']))
            window['txstatus'].update(response)
        except Exception as e:
            print(e)
            window['txstatus'].update('Exception occurred')
        # printStr =

    if event == '5.Print Chain':
        try:
            bc_info = cli.print_chain(bc)
            bc_string = ''
            for block in bc_info:
                bc_string = bc_string + str(block)
            new_chain_details = bc_string
        except:
            new_chain_details = "Error occurred in Printing chain!"
        window[chain_details].update(new_chain_details)




window.close()

