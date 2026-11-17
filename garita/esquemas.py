"""
Esquemas Pydantic de las salidas estructuradas del LLM.

El modelo responde en JSON (`response_format={"type": "json_object"}`, como en motor.py
del HW3) y cada respuesta se valida aqui antes de tocar una tabla. Si no valida, se
reintenta una vez mandandole el error; si vuelve a fallar, el proceso queda con
`error` y no entra al benchmark. Un numero inventado en silencio es peor que un hueco.

Los campos son los que importan para comparar precios y requisitos: cuantos puestos,
de cuantas horas, si van armados, cuanto dura el servicio y que perfil se exige. Nada
de personas: el perfil es el requisito del comprador, no datos de un vigilante.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ===== HERRAMIENTA 08 · LLMs con salidas estructuradas =====
# --- 08.1 Esquemas: lo que el modelo debe devolver al leer unas Bases
class Puesto(BaseModel):
    descripcion: str = Field("", description="Sede o tipo de puesto, tal como aparece")
    cantidad: int = Field(ge=0, le=500)
    horas_por_dia: float = Field(ge=0, le=24)
    dias_por_semana: float = Field(7, ge=0, le=7)
    armado: bool | None = None


class Perfil(BaseModel):
    estatura_min_m: float | None = Field(None, ge=1.4, le=2.1)
    edad_min: int | None = Field(None, ge=16, le=70)
    edad_max: int | None = Field(None, ge=18, le=80)
    experiencia_min_meses: int | None = Field(None, ge=0, le=600)
    curso_sucamec: bool | None = None
    licencia_arma_l4: bool | None = None
    secundaria_completa: bool | None = None


class ExtraccionTDR(BaseModel):
    puede_extraer: bool
    motivo: str = ""
    puestos: list[Puesto] = Field(default_factory=list)
    n_agentes_total: int | None = Field(None, ge=0, le=5000)
    plazo_meses: float | None = Field(None, ge=0, le=60)
    incluye_supervisor: bool | None = None
    perfil: Perfil = Field(default_factory=Perfil)
    tipo_arma: str | None = None
    equipamiento: list[str] = Field(default_factory=list)
    confianza: Literal["alta", "media", "baja"] = "baja"
    evidencia: str = Field("", max_length=400)

    @field_validator("equipamiento", mode="before")
    @classmethod
    def _lista(cls, v):
        if v is None:
            return []
        return [v] if isinstance(v, str) else v


# --- 08.2 Esquemas: lo que el modelo devuelve al leer un documento del proveedor
class ExtraccionDocumento(BaseModel):
    tipo_documento: Literal["carta_fianza", "poliza", "autorizacion_sucamec",
                            "contrato", "otro"]
    numero: str | None = None
    emisor: str | None = Field(None, description="Banco, aseguradora o entidad que emite")
    empresa: str | None = Field(None, description="Empresa afianzada o asegurada")
    ruc_empresa: str | None = None
    beneficiario: str | None = None
    monto: float | None = Field(None, ge=0)
    moneda: Literal["PEN", "USD", "otra"] | None = None
    fecha_emision: str | None = Field(None, description="AAAA-MM-DD")
    fecha_vencimiento: str | None = Field(None, description="AAAA-MM-DD")
    objeto: str | None = Field(None, max_length=300)
    observaciones: str | None = Field(None, max_length=300)


# --- 08.3 Esquemas: el pedido del cliente escrito en lenguaje natural
class PedidoTexto(BaseModel):
    departamento: str | None = None
    provincia: str | None = None
    tipo_sitio: Literal["mina", "campamento", "puerto", "planta", "almacen",
                        "oficina", "otro"] | None = None
    modalidad: Literal["VIGILANCIA PRIVADA", "PROTECCION PERSONAL",
                       "TRANSPORTE DE DINERO Y VALORES"] = "VIGILANCIA PRIVADA"
    con_armas: bool | None = None
    n_puestos: int | None = Field(None, ge=0, le=500)
    horas_por_dia: int | None = Field(None, ge=1, le=24)
    dias_por_semana: int | None = Field(None, ge=1, le=7)
    plazo_meses: int | None = Field(None, ge=1, le=60)
    equipamiento: list[str] = Field(default_factory=list)
    notas: str = ""
