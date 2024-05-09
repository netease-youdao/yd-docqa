# -*- coding: utf-8 -*-

import redis
from tqdm import tqdm

redis_conn = redis.Redis(host='localhost', port=6379, db=0)

# keys_to_delete = redis_conn.keys('*362bd332edc44170fb81d73fe80e5f35*') # LLM-augmenter
# # keys_to_delete = redis_conn.keys('*1c7a4c0c224e4f2b4654c07efe85f823*') # maskrcnn
keys_to_delete = redis_conn.keys('*eb00ee1cacec4cdc5fdb41beff58f944*') # BERT
# keys_to_delete = redis_conn.keys('*5fb8c75760f0ac40420397be90505395*') # memprompt
# keys_to_delete = redis_conn.keys('*d2daf4009e85fc4746590d315c7f4cae*') # OpenAI闭门讨论会
# keys_to_delete = redis_conn.keys('????????????????????????????????')
for key in tqdm(keys_to_delete):
    print(key)
    redis_conn.delete(key)

# keys_to_delete = redis_conn.keys("('????????????????????????????????', *, '*')")
# # keys_to_delete = redis_conn.keys("('5fb8c75760f0ac40420397be90505395', *, '*')")
# for key in tqdm(keys_to_delete):
    # # print(key)
    # redis_conn.delete(key)

# keys_to_delete = redis_conn.keys("('????????????????????????????????', '*')")
# # keys_to_delete = redis_conn.keys("('5fb8c75760f0ac40420397be90505395', '*')")
# for key in tqdm(keys_to_delete):
    # # print(key)
    # redis_conn.delete(key)
