# Archivador de Sitios Web con Ejecución de JavaScript y Autenticación Manual

Este proyecto permite archivar un sitio web estático tras haber ejecutado el JavaScript en un navegador sin interfaz gráfica (headless) utilizando Playwright. Además, ofrece la opción de autenticar manualmente antes de realizar el scrapping, lo cual es útil para sitios protegidos por autenticación (por ejemplo, un Google Sites privado).

## Características

- **Ejecución de JavaScript**: Utiliza Playwright para cargar la página en un navegador headless, ejecutando el JS y obteniendo el estado final del DOM.
- **Archivos autosuficientes**: Incrusta imágenes y hojas de estilo (CSS) directamente en el HTML mediante Data URIs, resultando en archivos `.html` autosuficientes.
- **Eliminar JavaScript y enlaces externos**: Remueve scripts y atributos `on...` para obtener HTML completamente estático, y elimina los enlaces externos.
- **Estructura local**: Las páginas internas del mismo dominio se archivan siguiendo la estructura del sitio, con enlaces locales actualizados.
- **Soporte para cookies y headers desde `curl`**: Opcionalmente, se pueden cargar cookies en formato JSON o reproducir headers desde un comando `curl`.
- **Autenticación manual opcional**: Inicie sesión manualmente en el navegador no headless antes de ejecutar el scrapping, guardando el estado de la sesión. Posteriormente, puede ejecutar el scrapping en modo headless utilizando las credenciales ya almacenadas.

## Requerimientos

- Python 3.7 o superior
- `pip` para gestionar paquetes
- Conexión a Internet
- Playwright y un navegador compatible (Chromium por defecto)
  
Instale las dependencias:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Uso

Ejemplo sin autenticación y sin cookies:
```bash
python script.py https://sites.google.com/example -o archivado
```

### Usando cookies

Si el sitio requiere cookies, puede proporcionar un archivo JSON con cookies en el formato previamente explicado:
```json
[
  {
    "name": "NID",
    "value": "valor_de_la_cookie",
    "domain": ".example.com",
    "path": "/",
    "expires": 1749591759.707042,
    "httpOnly": true,
    "secure": true,
    "sameSite": "Lax"
  }
]
```
Luego:
```bash
python script.py https://sites.google.com/example -o archivado --cookies cookies.json
```

### Usando headers desde curl

Si tiene un archivo con un comando `curl` (ejemplo: `curl.txt`) que contiene cabeceras `-H` o `--header`, puede replicar esos headers:
```bash
python script.py https://sites.google.com/example --curl curl.txt
```

### Autenticación manual

Para sitios que requieren autenticación compleja (ej: Google Sites privados), puede iniciar sesión manualmente:

1. Ejecute con `--login`:
   ```bash
   python script.py "https://sites.google.com/example" --login
   ```
   
   Esto abrirá un navegador no headless. Inicie sesión con sus credenciales en la página que se abre. Una vez autenticado, vuelva a la terminal y presione Enter. Esto guardará el estado en `state.json`.

2. Ahora puede ejecutar el scrapping en modo headless utilizando el estado guardado:
   ```bash
   python script.py "https://sites.google.com/example"
   ```
   
   De esta forma, el script utilizará la sesión guardada para acceder a páginas protegidas sin necesidad de volver a iniciar sesión.

## ¿Qué hace el script?

1. **Inicia un navegador con Playwright** (headless o no, según la opción).  
2. **Opcionalmente, autentica manualmente** y guarda el estado.
3. **Carga las páginas en el navegador**, esperando a que no haya actividad de red, ejecutando todo el JavaScript.
4. **Obtiene el HTML final** y lo procesa con BeautifulSoup:
   - Incrusta imágenes y CSS.
   - Ajusta enlaces internos para apuntar a los archivos locales archivados.
   - Elimina enlaces externos y JavaScript.
5. **Crea una estructura local** con el sitio archivado y recorre todos los enlaces internos.

### Casos de uso

- **Archivo de sitios internos o protegidos**: Guardar una versión offline de un Google Sites privado tras autenticar.
- **Auditorías o respaldos**: Preservar el estado final visible para usuarios autenticados.
- **Revisión sin conexión**: Tener una copia navegable del sitio con el contenido autenticado sin requerir conexión ni volver a iniciar sesión.

## Nota

- Algunos sitios pueden implementar flujos de autenticación muy complejos, requerir cookies o tokens no triviales. Este proceso facilita el acceso, pero no garantiza 100% de compatibilidad con todos los métodos de autenticación.
- Asegúrese de cumplir con las políticas y términos del sitio antes de archivarlo. Este proyecto es para propósitos legítimos, educativos y de respaldo.