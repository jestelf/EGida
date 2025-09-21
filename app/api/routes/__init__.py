from fastapi import APIRouter

from app.api.routes import auth, edges, graph, groups, health, invites, map as map_routes, nodes, organizations, spheres

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(map_routes.router, prefix="/map", tags=["map"])
api_router.include_router(nodes.router, prefix="/nodes", tags=["nodes"])
api_router.include_router(edges.router, prefix="/edges", tags=["edges"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(groups.router, tags=["groups"])
api_router.include_router(invites.router, prefix="/invites", tags=["invites"])
api_router.include_router(spheres.router, prefix="/spheres", tags=["spheres"])
api_router.include_router(graph.router, prefix="/graph", tags=["graph"])

__all__ = ["api_router"]
