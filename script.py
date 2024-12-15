import os
import sys
import asyncio
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import base64
import argparse
import json
import shlex
import time
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

STATE_FILE = "state.json"

def make_filename_from_url(url, output_dir):
    parsed = urlparse(url)
    domain = parsed.netloc
    path = parsed.path.lstrip('/')

    if not path:
        path = 'index.html'
    else:
        parts = path.split('/')
        # Asegurar extensión .html
        if not parts[-1].endswith('.html'):
            if '.' not in parts[-1]:
                parts[-1] += '.html'
            else:
                if not parts[-1].endswith('.html'):
                    parts[-1] += '.html'
        path = os.path.join(*parts)

    return os.path.join(output_dir, domain, path)

def ensure_dir_for_file(filepath):
    directory = os.path.dirname(filepath)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def is_same_domain(base_url, new_url):
    return urlparse(base_url).netloc == urlparse(new_url).netloc

def embed_resources(soup, page_url):
    # Incrustar imágenes
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src')
        if src:
            abs_url = urljoin(page_url, src)
            try:
                img_data = requests.get(abs_url, timeout=10)
                if img_data.status_code == 200:
                    mime_type = img_data.headers.get('Content-Type') or 'image/png'
                    data_uri = f"data:{mime_type};base64," + base64.b64encode(img_data.content).decode('utf-8')
                    img_tag['src'] = data_uri
            except:
                pass

    # Incrustar CSS externo
    for link_tag in soup.find_all('link', rel='stylesheet'):
        href = link_tag.get('href')
        if href:
            abs_url = urljoin(page_url, href)
            try:
                css_data = requests.get(abs_url, timeout=10)
                if css_data.status_code == 200:
                    style_tag = soup.new_tag('style')
                    style_tag.string = css_data.text
                    link_tag.replace_with(style_tag)
            except:
                pass

def map_cookie(cookie):
    pw_cookie = {
        "name": cookie["name"],
        "value": cookie["value"],
        "domain": cookie["domain"],
        "path": cookie["path"],
        "httpOnly": cookie.get("httpOnly", False),
        "secure": cookie.get("secure", False)
    }

    expires = cookie.get("expires", None)
    if expires is not None and expires != -1:
        pw_cookie["expires"] = int(expires)

    sameSite = cookie.get("sameSite", None)
    if sameSite is not None and sameSite in ["Strict", "Lax", "None"]:
        pw_cookie["sameSite"] = sameSite

    return pw_cookie

def parse_curl_headers(curl_content):
    tokens = shlex.split(curl_content)
    headers = {}
    for i, t in enumerate(tokens):
        if t in ("-H", "--header"):
            if i + 1 < len(tokens):
                header_line = tokens[i + 1]
                if ':' in header_line:
                    name, value = header_line.split(':', 1)
                    name = name.strip()
                    value = value.strip()
                    headers[name] = value
    return headers

async def process_page(url, start_url, output_dir, visited, page, context, force_html=False):
    # Remover la barra inclinada final de la URL si está presente
    if url.endswith('/'):
        url = url[:-1]
    # Ignorar URLs con fragmentos (#)
    if '#' in url:
        print(f"Ignorando enlace con fragmento: {url}")
        return
    if url in visited:
        return
    visited.add(url)

    print("Descargando y renderizando:", url)
    html = None
    try:
        await page.goto(url, timeout=300000)
        await page.wait_for_load_state("networkidle", timeout=300000)
        html = await page.content()

        # Obtener cookies actuales del contexto, luego volver a agregarlas para "refrescar"
        current_cookies = await context.cookies()
        await context.clear_cookies()
        await context.add_cookies(current_cookies)

    except PlaywrightTimeoutError:
        print(f"Error: No se pudo guardar la página por timeout: {url}")
        if force_html:
            # Intentar obtener contenido parcial
            try:
                html = await page.content()
                print("Se guardará el HTML parcial de la página.")
            except Exception as e:
                print(f"No se pudo obtener contenido parcial: {e}")
                return
        else:
            return
    except Exception as e:
        print(f"Error al procesar {url}: {e}")
        if force_html:
            try:
                html = await page.content()
                print("Se guardará el HTML parcial de la página a pesar del error.")
            except Exception as e:
                print(f"No se pudo obtener contenido parcial: {e}")
                return
        else:
            return

    if html is None:
        return

    soup = BeautifulSoup(html, 'html.parser')
    embed_resources(soup, url)

    # Ajustar enlaces y recolectar links internos
    links_to_follow = []
    for tag in soup.find_all(['a', 'div']):
        href = tag.get('href')
        data_url = tag.get('data-url')

        # Procesar href
        if href:
            abs_link = urljoin(url, href)  # Convertir a enlace absoluto
            if is_same_domain(start_url, abs_link):
                local_path = make_filename_from_url(abs_link, output_dir)
                current_file_path = make_filename_from_url(url, output_dir)
                local_rel_path = os.path.relpath(local_path, os.path.dirname(current_file_path))
                tag['href'] = local_rel_path  # Reemplazar href con la ruta relativa
                links_to_follow.append(abs_link)

        # Procesar data-url
        if data_url:
            abs_data_url = urljoin(url, data_url)  # Convertir a enlace absoluto
            if is_same_domain(start_url, abs_data_url):
                local_path = make_filename_from_url(abs_data_url, output_dir)
                current_file_path = make_filename_from_url(url, output_dir)
                local_rel_path = os.path.relpath(local_path, os.path.dirname(current_file_path))
                tag['data-url'] = local_rel_path  # Reemplazar data-url con la ruta relativa

    # Reemplazar en el HTML todos los enlaces a la página original
    html = str(soup)
    html = html.replace(url, '')

    output_path = make_filename_from_url(url, output_dir)
    ensure_dir_for_file(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # Si no hubo error, seguimos con enlaces
    if html is not None:
        for link in links_to_follow:
            await process_page(link, start_url, output_dir, visited, page, context, force_html=force_html)


async def login_manually(playwright, start_url, extra_http_headers):
    # Lanzar navegador no headless para login manual
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(extra_http_headers=extra_http_headers)
    page = await context.new_page()

    print(f"Abra la ventana del navegador y autentíquese en {start_url}. Luego regrese a esta terminal y presione Enter.")
    await page.goto(start_url, timeout=60000)

    input("Presione Enter una vez haya terminado de iniciar sesión.")

    # Guardar estado
    await context.storage_state(path=STATE_FILE)

    await context.close()
    await browser.close()

async def main():
    start_time = time.time()  # Tiempo de inicio

    parser = argparse.ArgumentParser(description='Archiva un sitio web tras ejecutar JS, con opciones de login manual y forzar HTML parcial.')
    parser.add_argument('site_url', help='URL del sitio a archivar. Ej: http://ejemplo.com')
    parser.add_argument('--output', '-o', default='archivado', help='Directorio de salida (por defecto: archivado)')
    parser.add_argument('--cookies', '-c', help='Ruta a un archivo JSON con las cookies')
    parser.add_argument('--curl', help='Ruta a un archivo con un comando curl, desde el cual se copiarán los headers')
    parser.add_argument('--login', action='store_true', help='Realizar login manual antes del scrapping')
    parser.add_argument('--force-html', action='store_true', help='Forzar la creación del HTML aunque la página no termine de cargar (parcial)')
    args = parser.parse_args()

    start_url = args.site_url
    output_dir = args.output
    visited = set()

    extra_http_headers = {}
    if args.curl and os.path.isfile(args.curl):
        with open(args.curl, 'r', encoding='utf-8') as f:
            curl_content = f.read()
        extra_http_headers = parse_curl_headers(curl_content)

    # Tamaño de la ventana (75% del tamaño estándar)
    viewport_width = int(1920 * 0.75)  # Ancho
    viewport_height = int(1080 * 0.75)  # Alto

    async with async_playwright() as p:
        if args.login:
            # Realizar login manual
            await login_manually(p, start_url, extra_http_headers)

        # Ahora lanzar en modo headless con el estado guardado (si existe)
        context_kwargs = {
            "extra_http_headers": extra_http_headers,
            "viewport": {"width": viewport_width, "height": viewport_height},  # Configurar el viewport
        }
        if os.path.exists(STATE_FILE):
            context_kwargs["storage_state"] = STATE_FILE

        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(**context_kwargs)

        # Si se especificaron cookies iniciales y no se hizo login manual
        if args.cookies and os.path.isfile(args.cookies) and not args.login:
            with open(args.cookies, 'r', encoding='utf-8') as cf:
                cookies_list = json.load(cf)
            pw_cookies = [map_cookie(c) for c in cookies_list if c.get("name") and c.get("value")]
            await context.add_cookies(pw_cookies)

        page = await context.new_page()

        await process_page(start_url, start_url, output_dir, visited, page, context, force_html=args.force_html)

        await browser.close()

    end_time = time.time()  # Tiempo final
    total_time = end_time - start_time
    print(f"Proceso completado. Tiempo total: {total_time:.2f} segundos.")


if __name__ == "__main__":
    asyncio.run(main())
