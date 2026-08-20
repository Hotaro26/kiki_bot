from aiohttp import web
import os

async def handle(request):
    return web.Response(text="Ace Study Bot is alive and well!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render assigns a dynamic port via the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    
    await site.start()
    print(f"Keep-alive web server started on port {port}")
