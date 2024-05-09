import tiktoken


def num_tokens_from_messages(message_texts, model="gpt-3.5-turbo-0301"):
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = 0
    for message in message_texts:
        # num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        # for key, value in message.items():
        num_tokens += len(encoding.encode(message))
            # if key == "name":  # if there's a name, the role is omitted
                # num_tokens += -1  # role is always required and always 1 token
    # num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens


async def get_async_llm_answer(llm, content, history, streaming):
    nonstream_answer = ''
    async for reply in llm.generatorAnswer(content, history=history, streaming=streaming):
        # return reply.llm_output['answer']
        nonstream_answer += reply.history[-1][1]
    return nonstream_answer
