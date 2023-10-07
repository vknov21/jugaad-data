from jugaad_data.nse import NSELive
import sys
from PyQt5 import QtWidgets, QtTest, QtCore
from MyMainWindow import MyMainWindow, BaseWorkerThread
import logging

n = NSELive()


def nse_session():
    try:
        price_list = [
            get_stock_price("TCS"),
            get_option_strike_price("TCS", 3740, "CE"),
            # get_stock_price("GOKEX"),
        ]
    except Exception as e:
        logging.exception(e)
        return ""
    return "•".join(price_list)


def get_option_strike_price(stock, strike_price, direction):
    option_chain = n.option_chain_equities(stock)['filtered']['data']
    strike_price_1 = option_chain[0]['strikePrice']
    strike_price_2 = option_chain[1]['strikePrice']
    idx = (strike_price - strike_price_1) // (strike_price_2 - strike_price_1)
    try:
        return str(option_chain[idx][direction]['lastPrice']) or ''
    except Exception:
        print(option_chain, idx)
        raise


def get_stock_price(stock):
    return str(n.stock_quote(stock)['priceInfo']['lastPrice'])


def setLabelTextandAdjust(worker, text):
    QtCore.QMetaObject.invokeMethod(worker.window.label, "setText", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(str, text))
    QtTest.QTest.qWait(400)
    worker.window.label.adjustSize()
    worker.resizeMainWindow(worker.window.label.size().width(), worker.window.label.size().height())


class WorkerThread(BaseWorkerThread):
    def run(self):
        while True:
            text = str(nse_session())
            setLabelTextandAdjust(self, text)
            # if n.market_status()['marketState'][0]['marketStatus'] == 'Closed':
            #     print(n.market_status()['marketState'][0]['marketStatus'])
            #     QtTest.QTest.qWait(900000)
            #     continue
            QtTest.QTest.qWait(30000)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = MyMainWindow(workerThread=WorkerThread)
    MainWindow.show()
    sys.exit(app.exec_())


# n = NSELive()
# try:
#     stock_price = n.stock_quote("ADANIPORTS")['priceInfo']['lastPrice']
#     import pdb; pdb.set_trace()
#     nifty = n.live_index("ADANIPORTS")
#     option_chain = n.option_chain_equities("ADANIPORTS")
#     li = [(option['CE']['changeinOpenInterest'], option['PE']['changeinOpenInterest']) for option in option_chain['filtered']['data']]
#     print(f"[{localtime().tm_min}.{localtime().tm_sec}]", "PCR:", round(sum([i[1] for i in li]) / sum([i[0] for i in li]), 2),
#             "(CE_OI:", option_chain['filtered']['CE']['totOI'], "|", option_chain['filtered']['PE']['totOI'], ":PE_OI)", "DIFF_OI:",
#             option_chain['filtered']['PE']['totOI'] - option_chain['filtered']['CE']['totOI'],
#             "DIFF_VOL:", option_chain['filtered']['PE']['totVol'] - option_chain['filtered']['CE']['totVol'],
#             f"({option_chain['filtered']['PE']['totVol']} | {option_chain['filtered']['CE']['totVol']})")
# except Exception as e:
#     print(str(e), option_chain)
#     n = NSELive()

# try:
#     nifty = n.live_index("ADANIPORTS")
#     option_chain = n.option_chain_equities("ADANIPORTS")
#     li = [(option['CE']['changeinOpenInterest'], option['PE']['changeinOpenInterest']) for option in option_chain['filtered']['data']]
#     print(f"[{localtime().tm_min}.{localtime().tm_sec}]", "PCR:", round(sum([i[1] for i in li]) / sum([i[0] for i in li]), 2),
#             "(CE_OI:", option_chain['filtered']['CE']['totOI'], "|", option_chain['filtered']['PE']['totOI'], ":PE_OI)", "DIFF_OI:",
#             option_chain['filtered']['PE']['totOI'] - option_chain['filtered']['CE']['totOI'],
#             "DIFF_VOL:", option_chain['filtered']['PE']['totVol'] - option_chain['filtered']['CE']['totVol'],
#             f"({option_chain['filtered']['PE']['totVol']} | {option_chain['filtered']['CE']['totVol']})")
#     return
# except Exception as e:
#     print(str(e), option_chain)
#     n = NSELive()
