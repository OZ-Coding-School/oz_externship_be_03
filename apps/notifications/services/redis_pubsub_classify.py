import asyncio
import time

import redis.asyncio as redis

r = redis.Redis(host="redis",port=6379)

p = r.pubsub()

STOPWORD = "STOP"

async def async_pub():
    ''' 3초마다 채널에 메시지 발신'''

    async with r :
        try:
            while True:
                message = f"send message: {time.time()}"
                await r.publish("my-async-channel", message)
                await asyncio.sleep(3)

        except redis.RedisError as e:
            print(f"Redis error occured: {e}")


async def reader(channel:redis.client.PubSub):
    while True:
        message = await channel.get_message(ignore_subscribe_messages=True)
        if message is not None:
            print(f"(Reader)Message Received: {message}",flush=True)
            if message["data"].decode() == STOPWORD:
                print("(Reader) STOP")
                break

async def main():
    async with r.pubsub() as pubsub:
        await pubsub.subscribe("my-async-channel")
        await asyncio.create_task(reader(pubsub))



