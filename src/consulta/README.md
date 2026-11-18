# Aplicación de consulta

Esta pantalla pregunta el perfil de un cliente. No abre el archivo del modelo ni importa el entrenamiento. Solo llama al API que usted publicó en [src/api/README.md](../api/README.md).

## Paso 1: Tener el API encendido

Siga la guía del API hasta ver Swagger en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Paso 2: Encender la consulta

En otra terminal, dentro de `src/consulta`:

```bash
py -3 -m pip install -r requirements.txt
set MODELO_URL=http://127.0.0.1:8000
set MODELO_TIMEOUT=5
py -3 -m uvicorn app:app --host 127.0.0.1 --port 8080
```

En PowerShell, los dos `set` se escriben así:

```powershell
$env:MODELO_URL = "http://127.0.0.1:8000"
$env:MODELO_TIMEOUT = "5"
```

Abra [http://127.0.0.1:8080](http://127.0.0.1:8080), complete el formulario y pulse **Consultar perfil**.

## Paso 3: Qué hace ante fallos

| Situación | Qué muestra la pantalla |
|---|---|
| El API tarda más de 5 segundos | Dice que el servicio no respondió a tiempo |
| El API está apagado o la URL es incorrecta | Dice que no pudo conectar y pide revisar `MODELO_URL` |
| El API responde 422 | Dice que rechazó los datos |
| El API responde otro error | Muestra el código de error |
| La respuesta no es JSON o no trae `predicciones` | Dice que la respuesta no sirve |

`MODELO_URL` tiene que ser la dirección del API. No ponga aquí la carpeta `artefactos`.

## Docker

Si levantó los dos servicios con `docker compose up --build` desde la raíz del repositorio, la consulta ya apunta a `http://modelo:8000` y se abre en el puerto 8080.
