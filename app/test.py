import asyncio

async def waiter(event):
    print('waiting for it ...')
    await event.wait()
    print('... got it 1!')
    await event.wait()
    
    
    print('... got it 2!')
    await event.wait()
    print('... got it 3!')
    await event.wait()
    print('... got it 4!')

async def main():
    # Create an Event object.
    event = asyncio.Event()

    # Spawn a Task to wait until 'event' is set.
    waiter_task = asyncio.create_task(waiter(event))

    # Sleep for 1 second and set the event.
    await asyncio.sleep(1)
    print('1')
    event.set()
    print('2')
    event.clear()
    print('3')
    await asyncio.sleep(1)
    
    
    print('4')
    event.set()
    print('5')
    await asyncio.sleep(3)
    
    
    print('6')
    event.clear()
    print('7')
    await asyncio.sleep(1)
    print('8')
    event.clear()

    # Wait until the waiter task is finished.
    await waiter_task

async def waiter2(event):
	print('waiting for it ...')
	async with event:
		await event.wait()
		print('... got it 1!')
	async with event:
		await event.wait()
		print('... got it 2!')
	async with event:
		await event.wait()
		print('... got it 3!')
	async with event:
		await event.wait()
		print('... got it 4!')

async def main2():
	event = asyncio.Condition()

	# Spawn a Task to wait until 'event' is set.
	waiter_task = asyncio.create_task(waiter2(event))

	# Sleep for 1 second and set the event.
	await asyncio.sleep(1)
	print('1')
	async with event:
		event.notify()
	print('2')
	#event.clear()
	print('3')
	await asyncio.sleep(1)
	
	
	print('4')
	async with event:
		event.notify()
	print('5')
	await asyncio.sleep(3)
	
	
	print('6')
	#event.clear()
	print('7')
	await asyncio.sleep(1)
	print('8')
	#event.clear()

	# Wait until the waiter task is finished.
	await waiter_task

#asyncio.run(main())
asyncio.run(main2())
