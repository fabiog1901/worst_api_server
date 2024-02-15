from fastapi import APIRouter, BackgroundTasks, Security, Body
from fastapi.responses import HTMLResponse
from typing import Annotated, Any, Type
from uuid import UUID
from apiserver.models import User, BaseFields
import inspect
import apiserver.dependencies as dep
import apiserver.service as svc
import datetime as dt


class WorstRouter(APIRouter):
    def __init__(
        self,
        instance_type: str,
        default_model: Type[BaseFields],
        overview_model: Type[BaseFields],
        update_model: Type[BaseFields],
    ) -> None:
        super().__init__(
            prefix=f"/{instance_type}",
            tags=[instance_type],
        )

        @self.get(
            "",
            dependencies=[
                Security(dep.get_current_user, scopes=["worst_instances_read"])
            ],
            description="Required permission: `worst_instances_read`",
        )
        async def get_all_instances() -> list[overview_model] | None:
            return svc.get_all_instances(instance_type)

        @self.get(
            "/{id}",
            dependencies=[
                Security(dep.get_current_user, scopes=["worst_instances_read"])
            ],
            description="Required permission: `worst_instances_read`",
        )
        async def get_instance(
            id: UUID,
        ) -> default_model | None:
            return svc.get_instance(instance_type, id)

        @self.get(
            "/{id}/children",
            dependencies=[
                Security(dep.get_current_user, scopes=["worst_instances_read"])
            ],
            description="Required permission: `worst_instances_read`",
        )
        async def get_all_children(
            id: UUID,
        ) -> dict | None:
            return svc.get_all_children(instance_type, id)

        @self.get(
            "/{id}/parent_chain",
            dependencies=[
                Security(dep.get_current_user, scopes=["worst_instances_read"])
            ],
            description="Required permission: `worst_instances_read`",
        )
        async def get_parent_chain(
            id: UUID,
        ) -> list | None:
            return svc.get_parent_chain(instance_type, id)

        @self.get(
            "/{id}/{children_instance_type}",
            dependencies=[
                Security(dep.get_current_user, scopes=["worst_instances_read"])
            ],
            description="Required permission: `worst_instances_read`",
        )
        async def get_all_children_for_model(
            id: UUID,
            children_instance_type: str,
        ) -> list | None:
            return svc.get_all_children_for_model(
                instance_type, id, children_instance_type
            )

        @self.post(
            "",
            description="Required permission: `worst_instances_create`",
        )
        async def create_instance(
            model: update_model,
            current_user: Annotated[
                User, Security(dep.get_current_user, scopes=["worst_instances_create"])
            ],
            bg_task: BackgroundTasks,
        ) -> default_model | None:
            x = svc.create_instance(instance_type, current_user, model)

            if x:
                bg_task.add_task(
                    svc.log_event,
                    instance_type,
                    dt.datetime.utcnow(),
                    current_user,
                    inspect.currentframe().f_code.co_name,  # type: ignore
                    x.model_dump_json(),
                )

                bg_task.add_task(
                    svc.add_documents, self.__get_search_documents(instance_type, x)
                )

            return x

        @self.put(
            "",
            description="Required permission: `worst_instances_update`",
        )
        async def update_instance(
            model: update_model,
            current_user: Annotated[
                User, Security(dep.get_current_user, scopes=["worst_instances_update"])
            ],
            bg_task: BackgroundTasks,
        ) -> default_model | None:
            x = svc.update_instance(instance_type, current_user, model)

            if x:
                bg_task.add_task(
                    svc.log_event,
                    instance_type,
                    dt.datetime.utcnow(),
                    current_user,
                    inspect.currentframe().f_code.co_name,  # type: ignore
                    x.model_dump_json(),
                )

                bg_task.add_task(
                    svc.add_documents, self.__get_search_documents(instance_type, x)
                )

            return x

        @self.patch(
            "/{id}",
            description="Required permission: `worst_instances_patch`",
        )
        async def partial_update_instance(
            id: UUID,
            field: Annotated[str, Body()],
            value: Annotated[Any, Body()],
            current_user: Annotated[
                User, Security(dep.get_current_user, scopes=["worst_instances_patch"])
            ],
            bg_task: BackgroundTasks,
        ) -> default_model | None:
            x = svc.partial_update_instance(
                instance_type, current_user, id, field, value
            )

            if x:
                bg_task.add_task(
                    svc.log_event,
                    instance_type,
                    dt.datetime.utcnow(),
                    current_user,
                    inspect.currentframe().f_code.co_name,  # type: ignore
                    x.model_dump_json(),
                )

                bg_task.add_task(
                    svc.add_documents, self.__get_search_documents(instance_type, x)
                )

            return x

        @self.delete(
            "/{id}",
            description="Required permission: `worst_instances_delete`",
        )
        async def delete_instance(
            id: UUID,
            current_user: Annotated[
                User, Security(dep.get_current_user, scopes=["worst_instances_delete"])
            ],
            bg_task: BackgroundTasks,
        ) -> default_model | None:
            x: default_model = svc.delete_instance(instance_type, id)

            if x:
                bg_task.add_task(
                    svc.log_event,
                    instance_type,
                    dt.datetime.utcnow(),
                    current_user,
                    inspect.currentframe().f_code.co_name,  # type: ignore
                    x.model_dump_json(),
                )

                bg_task.add_task(svc.delete_document, instance_type + "_" + str(x.id))
            return x

    def __get_search_documents(self, instance_type: str, x: Type[BaseFields]) -> list:
        return [
            {"comp_id": instance_type + "_" + str(x.id)}
            | x.model_dump(
                mode="json",
                exclude=[
                    "id",
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                    "permissions",
                    "parent_type",
                    "parent_id",
                    "owned_by",
                ],
                exclude_unset=True,
                exclude_none=True,
            )
        ]
