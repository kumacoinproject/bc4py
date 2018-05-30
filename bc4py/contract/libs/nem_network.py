#from nem_python import NemConnect
#from threading import Thread


#nem = NemConnect()
#Thread(target=nem.start, daemon=True).start()


#def nem_account_info(ck):
#    return nem.get_account_info(ck)


#def nem_account_owned_mosaic(ck):
#    return nem.get_account_owned_mosaic(ck)


#def nem_account_transfer_newest(ck, call_name=nem.TRANSFER_INCOMING):
#    return nem.get_account_transfer_newest(ck, call_name)


#def nem_account_transfer_all(ck, call_name=nem.TRANSFER_INCOMING):
#    return nem.get_account_transfer_all(ck, call_name)


#def nem_last_chain():
#    return nem.get_last_chain()


__price__ = {
    #"nem_account_info": 1000,
    #"nem_account_owned_mosaic": 5000,
    #"nem_account_transfer_newest": 5000,
    #"nem_account_transfer_all": 50000,
    #"nem_last_chain": 1000,
}

__all__ = tuple(__price__)
