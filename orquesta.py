# orquesta_v3.py  ← REEMPLAZA TU ARCHIVO ACTUAL
import json
import random
import os
import logging
import traceback
from datetime import datetime
from collections import defaultdict
import pickle
from flask import Flask, request, jsonify, Blueprint

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Clase helper para puntuaciones (pickle-compatible)
class ScoreDict(dict):
    """Diccionario que retorna 0.5 por defecto para cualquier clave no existente"""
    def __missing__(self, key):
        return 0.5

class PuntuacionRoles(dict):
    """Diccionario de diccionarios de puntuaciones"""
    def __missing__(self, key):
        self[key] = ScoreDict()
        return self[key]

app = Blueprint('orquesta', __name__)

class OrquestaV3:
    def __init__(self, memory_file="orquesta_memory.pkl"):
        self.memory_file = memory_file
        self.load_memory()

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "rb") as f:
                    data = pickle.load(f)
                    self.ultima_asignacion = data.get("ultima_asignacion", {})
                    # Convertir dict normal a PuntuacionRoles
                    loaded_puntuacion = data.get("puntuacion_rol", {})
                    self.puntuacion_rol = PuntuacionRoles()
                    for nombre, roles in loaded_puntuacion.items():
                        self.puntuacion_rol[nombre] = ScoreDict(roles)
                    self.feedback_count = data.get("feedback_count", 0)
                    self.feedback_history = data.get("feedback_history", [])
                print(f"Orquesta 3.0 cargada | {len(self.ultima_asignacion)} hermanos recordados | {len(self.feedback_history)} feedbacks")
            except Exception as e:
                logger.error(f"Error cargando memoria: {e}")
                self.reset_memory()
        else:
            print("Orquesta 3.0: Primera vez. ¡Hola mundo!")
            self.reset_memory()

    def reset_memory(self):
        self.ultima_asignacion = {}
        self.puntuacion_rol = PuntuacionRoles()
        self.feedback_count = 0
        self.feedback_history = []

    def save_memory(self):
        try:
            with open(self.memory_file, "wb") as f:
                pickle.dump({
                    "ultima_asignacion": self.ultima_asignacion,
                    "puntuacion_rol": dict(self.puntuacion_rol),
                    "feedback_count": self.feedback_count,
                    "feedback_history": self.feedback_history
                }, f)
            logger.info(f"✅ Memoria guardada: {len(self.ultima_asignacion)} hermanos, {self.feedback_count} feedbacks")
        except Exception as e:
            logger.error(f"❌ ERROR guardando memoria: {str(e)}")
            logger.error(traceback.format_exc())

    def semanas_desde_ultima(self, nombre, fecha_ref):
        if nombre not in self.ultima_asignacion:
            return 999
        ultima = datetime.fromisoformat(self.ultima_asignacion[nombre])
        ref = datetime.fromisoformat(fecha_ref)
        return max(1, (ref - ultima).days // 7)

    def asignar(self, payload, fecha_semana):
        logger.debug(f"Iniciando asignar() con fecha: {fecha_semana}")
        
        candidatos = payload.get("candidatos_publicador", [])
        logger.debug(f"Candidatos publicador: {len(candidatos)} encontrados")
        
        # Validar que se hayan enviado candidatos
        if not candidatos:
            logger.warning("⚠️  No se recibieron candidatos para asignar")
            logger.warning("Asegúrate de enviar 'candidatos_publicador' con al menos un candidato")
            logger.warning("Ejemplo: {'nombre': 'Juan Pérez', 'genero': 'M', 'roles': ['publicador']}")
        
        roles_generales = payload.get("roles_generales", {})
        logger.debug(f"Roles generales: {list(roles_generales.keys())}")
        
        actividades_raw = payload.get("actividades", [])
        logger.debug(f"Actividades: {len(actividades_raw)} encontradas")

        # === 1. Asignar roles generales ===
        roles_asignados = {}
        usados = set()

        for rol, lista in roles_generales.items():
            if not lista: continue
            candidatos_rol = [c for c in lista if c not in usados]
            if not candidatos_rol:
                roles_asignados[rol] = None
                continue

            # Puntaje: rotación + aprendizaje
            scores = []
            for nombre in candidatos_rol:
                semanas = self.semanas_desde_ultima(nombre, fecha_semana)
                aprendido = self.puntuacion_rol[nombre][rol]
                score = (semanas / 20.0) * 0.6 + aprendido * 0.4
                # Agregar nombre como tercer elemento para desempatar
                scores.append((score, nombre, nombre))

            logger.debug(f"Rol '{rol}': {len(scores)} candidatos, tipo primer score: {type(scores[0]) if scores else 'vacío'}")
            scores.sort(reverse=True)
            elegido = scores[0][1]  # El nombre está en posición 1
            roles_asignados[rol] = elegido
            usados.add(elegido)
            self.ultima_asignacion[elegido] = fecha_semana

        # === 2. Asignar actividades ===
        actividades = []

        for act in actividades_raw:
            tema = act["tema"]
            tema_upper = tema.upper()
            
            # Identificar sección SEAMOS MEJORES MAESTROS
            # Incluye: DE CASA EN CASA, PREDICACIÓN, REVISITA, CURSO BÍBLICO, DISCURSO, LMD, ANIME
            es_smc = any(palabra in tema_upper for palabra in [
                "DE CASA EN CASA", "PREDICACIÓN", "PREDICACION", "REVISITA", 
                "CURSO BÍBLICO", "CURSO BIBLICO", "DISCURSO", "LMD", "ANIME"
            ])
            
            # Filtrar candidatos disponibles
            disponibles = [c for c in candidatos if c["nombre"] not in usados]

            # Aplicar reglas de género según sección
            if es_smc:
                # SEAMOS MEJORES MAESTROS: preferir mujeres
                logger.debug(f"Tema SMC detectado: {tema}")
                mujeres = [c for c in disponibles if c["genero"] in ["F", "Mujer"]]
                hombres = [c for c in disponibles if c["genero"] in ["M", "Hombre"]]
                candidatos_pub = mujeres + hombres
                candidatos_ay = mujeres + hombres
            else:
                # TESOROS y NUESTRA VIDA CRISTIANA: solo hombres
                logger.debug(f"Tema no-SMC detectado: {tema}")
                candidatos_pub = [c for c in disponibles if c["genero"] in ["M", "Hombre"]]
                candidatos_ay = [c for c in candidatos_pub if "ayudante" in str(c.get("roles", "")).lower()]

            # Asignar publicador
            publicador = None
            if candidatos_pub:
                scores = []
                for c in candidatos_pub:
                    semanas = self.semanas_desde_ultima(c["nombre"], fecha_semana)
                    aprendido = self.puntuacion_rol[c["nombre"]]["publicador"]
                    score = (semanas / 20.0) * 0.5 + aprendido * 0.5
                    # Agregar nombre como tercer elemento para desempatar
                    scores.append((score, c["nombre"], c))
                
                scores.sort(reverse=True)
                publicador = scores[0][2]  # El objeto candidato está en posición 2
                usados.add(publicador["nombre"])
                self.ultima_asignacion[publicador["nombre"]] = fecha_semana

            # Asignar ayudante (si aplica)
            ayudante = None
            if "ayudante" in tema.lower() or es_smc:
                disponibles_ay = [c for c in candidatos_ay if c["nombre"] not in usados]
                if disponibles_ay:
                    ayudante = random.choice(disponibles_ay)
                    usados.add(ayudante["nombre"])

            actividades.append({
                "tema": tema,
                "publicador": {"nombre": publicador["nombre"], "genero": publicador["genero"]} if publicador else None,
                "ayudante": {"nombre": ayudante["nombre"], "genero": ayudante["genero"]} if ayudante else None
            })

        resultado = {
            "roles_generales": {
                "presidente": roles_asignados.get("presidente"),
                "oracion_inicio": roles_asignados.get("oracion_inicio"),
                "oracion_final": roles_asignados.get("oracion_final"),
                "conductor": roles_asignados.get("conductor"),
                "lector": roles_asignados.get("lector")
            },
            "actividades": actividades
        }

        self.save_memory()
        return resultado

# === Instancia global ===
orquesta = OrquestaV3()

# === Ruta principal: reemplaza 100% a OpenAI ===
@app.route("/v1/assign_meeting", methods=["POST"])
def assign_meeting():
    try:
        logger.info("=" * 80)
        logger.info("Nueva petición a /v1/assign_meeting")
        
        data = request.get_json()
        logger.info(f"Payload recibido: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if not data:
            logger.error("No se recibió JSON en la petición")
            return jsonify({"error": "No JSON"}), 400

        fecha = data.get("week_date", datetime.today().strftime("%Y-%m-%d"))
        logger.info(f"Fecha de semana: {fecha}")
        
        logger.info("Iniciando asignación...")
        resultado = orquesta.asignar(data, fecha)
        logger.info(f"Asignación exitosa: {json.dumps(resultado, indent=2, ensure_ascii=False)}")
        logger.info("=" * 80)
        
        return jsonify(resultado)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"ERROR CRÍTICO en assign_meeting: {str(e)}")
        logger.error(f"Tipo de error: {type(e).__name__}")
        logger.error("Traceback completo:")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        
        return jsonify({
            "error": str(e),
            "tipo": type(e).__name__,
            "traceback": traceback.format_exc()
        }), 500

# === Feedback con instrucciones de entrenamiento ===
@app.route("/v1/feedback", methods=["POST"])
def feedback():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON"}), 400
        
        week_date = data.get("week_date")
        gusto = data.get("gusto")
        instrucciones = data.get("instrucciones", "")
        comentarios = data.get("comentarios", "")
        ajustes = data.get("ajustes", {})  # Ej: {"nombre": "Juan", "rol": "presidente", "puntuacion": 0.8}
        
        # Guardar feedback en historial
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "week_date": week_date,
            "gusto": gusto,
            "instrucciones": instrucciones,
            "comentarios": comentarios,
            "ajustes": ajustes
        }
        
        orquesta.feedback_history.append(feedback_entry)
        orquesta.feedback_count += 1
        
        # Aplicar ajustes de puntuación si se proporcionan
        if ajustes and "nombre" in ajustes and "rol" in ajustes:
            nombre = ajustes["nombre"]
            rol = ajustes["rol"]
            puntuacion = ajustes.get("puntuacion", 0.5)
            orquesta.puntuacion_rol[nombre][rol] = puntuacion
            logger.info(f"Ajuste aplicado: {nombre} → {rol} = {puntuacion}")
        
        orquesta.save_memory()
        
        logger.info(f"Feedback recibido: {feedback_entry}")
        
        return jsonify({
            "msg": "Gracias por tu feedback. Las instrucciones han sido guardadas.",
            "total_feedbacks": orquesta.feedback_count,
            "feedback_guardado": feedback_entry
        })
        
    except Exception as e:
        logger.error(f"Error en feedback: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/v1/feedback/history", methods=["GET"])
def feedback_history():
    """Obtener historial de feedbacks"""
    try:
        limit = request.args.get("limit", 10, type=int)
        # Retornar los últimos N feedbacks
        recent_feedbacks = orquesta.feedback_history[-limit:] if orquesta.feedback_history else []
        
        return jsonify({
            "total": len(orquesta.feedback_history),
            "mostrando": len(recent_feedbacks),
            "feedbacks": recent_feedbacks
        })
    except Exception as e:
        logger.error(f"Error obteniendo historial: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/v1/status")
def status():
    return jsonify({
        "orquesta": "3.0",
        "estado": "funcionando perfectamente",
        "hermanos_recordados": len(orquesta.ultima_asignacion),
        "feedbacks": orquesta.feedback_count,
        "feedback_history_size": len(orquesta.feedback_history)
    })