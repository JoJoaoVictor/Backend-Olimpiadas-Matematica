import json
import re
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import JSONResponse


def camel_to_snake(name: str) -> str:
    """Converte camelCase para snake_case."""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel(name: str) -> str:
    """Converte snake_case para camelCase."""
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def convert_keys(data: Any, converter_func) -> Any:
    """Converte chaves de um dict usando a função fornecida."""
    if isinstance(data, dict):
        new_dict = {}
        for key, value in data.items():
            new_key = converter_func(key)
            new_dict[new_key] = convert_keys(value, converter_func)
        return new_dict
    elif isinstance(data, list):
        return [convert_keys(item, converter_func) for item in data]
    else:
        return data


async def compatibility_middleware(request: Request, call_next):
    """
    Middleware que permite compatibilidade entre frontend e backend.
    
    Frontend envia: camelCase (professorName)
    Backend espera: snake_case (professor_name)
    """
    
    # Se for uma requisição com body, converter camelCase → snake_case
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Ler body original
            body_bytes = await request.body()
            
            if body_bytes:
                # Converter para dict
                body_dict = json.loads(body_bytes)
                
                # Converter camelCase → snake_case
                converted_body = convert_keys(body_dict, camel_to_snake)
                
                # Substituir body da request
                request._body = json.dumps(converted_body).encode()
                
                # Log para debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"🔧 Convertido: {list(body_dict.keys())[:3]} → {list(converted_body.keys())[:3]}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Se não for JSON, deixar como está
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Erro no middleware de compatibilidade: {e}")
    
    # Processar request
    response = await call_next(request)
    
    # Se for uma resposta JSON, converter snake_case → camelCase
    if response.headers.get("content-type", "").startswith("application/json"):
        try:
            # Ler body da resposta
            response_body = response.body.decode() if response.body else "{}"
            
            if response_body and response_body != "null":
                # Converter para dict
                response_dict = json.loads(response_body)
                
                # Converter snake_case → camelCase
                camel_response = convert_keys(response_dict, snake_to_camel)
                
                # Criar nova resposta
                response = JSONResponse(
                    content=camel_response,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        except (json.JSONDecodeError, AttributeError):
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Erro ao converter resposta: {e}")
    
    return response