import inspect
import re

def cur_func_name():
    return inspect.currentframe().f_back.f_code.co_name

def sent_tokenize(x):
    sents_temp = re.split('(。|！|\!|\.|？|\?)', x)
    sents = []
    for i in range(len(sents_temp)//2):
        sent = sents_temp[2*i] + sents_temp[2*i+1]
        sents.append(sent)
    return sents
