from psycopg_pool import ConnectionPool
from psycopg.types.array import ListDumper
from psycopg.types.json import Jsonb, JsonbDumper
from typing import Any, Type
from uuid import UUID
import os
import datetime as dt
from apiserver.models import (
    Model,
    Report,
    pyd_models,
    BaseFields,
)


DB_URL = os.getenv("DB_URL")
DB_URL_DML = os.getenv("DB_URL_DML")
DB_URL_SELECT = os.getenv("DB_URL_SELECT")

SQL_RESERVED_WORDS = [
    "all",
    "analyse",
    "analyze",
    "and",
    "any",
    "array",
    "as",
    "asc",
    "asymmetric",
    "both",
    "case",
    "cast",
    "check",
    "collate",
    "column",
    "concurrently",
    "constraint",
    "create",
    "current_catalog",
    "current_date",
    "current_role",
    "current_schema",
    "current_time",
    "current_timestamp",
    "current_user",
    "default",
    "deferrable",
    "desc",
    "distinct",
    "do",
    "else",
    "end",
    "except",
    "false",
    "fetch",
    "for",
    "foreign",
    "from",
    "grant",
    "group",
    "having",
    "in",
    "index",
    "initially",
    "intersect",
    "into",
    "lateral",
    "leading",
    "limit",
    "localtime",
    "localtimestamp",
    "not",
    "nothing",
    "null",
    "offset",
    "on",
    "only",
    "or",
    "order",
    "placing",
    "primary",
    "references",
    "returning",
    "select",
    "session_user",
    "some",
    "symmetric",
    "table",
    "then",
    "to",
    "trailing",
    "true",
    "union",
    "unique",
    "user",
    "using",
    "variadic",
    "when",
    "where",
    "window",
    "with",
]

RESERVED_WORDS = [
    "id",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "name",
    "owned_by",
    "permissions",
    "tags",
    "parent_type",
    "parent_id",
    "attachments",
] + SQL_RESERVED_WORDS

if not DB_URL:
    raise EnvironmentError("DB_URL env variable not found!")


# the pool starts connecting immediately.
pool = ConnectionPool(DB_URL, kwargs={"autocommit": True})
dml_pool = ConnectionPool(DB_URL_DML, kwargs={"autocommit": True})
select_pool = ConnectionPool(DB_URL_SELECT, kwargs={"autocommit": True})


def log_event(
    model_name: str, ts: dt.datetime, username: str, action: str, details: str
):
    execute_stmt(
        """UPSERT INTO 
            internal.events (object, ts, username, action, details) 
        VALUES 
            (%s, %s, %s, %s, %s)
        """,
        (model_name, ts, username, action, details),
        returning_rs=False,
    )


def get_watch() -> int:
    return execute_stmt(
        "SELECT ts::INT8 FROM internal.watch AS OF SYSTEM TIME follower_read_timestamp() LIMIT 1",
    )[0]


def update_watch() -> None:
    # just refresh the entry to update column 'ts'
    execute_stmt("UPDATE internal.watch SET id=1 WHERE true", returning_rs=False)


def load_schema(ddl_filename):
    with open(ddl_filename) as f:
        execute_stmt(f.read(), returning_rs=False)


def get_fields(model) -> str:
    return ", ".join([x for x in model.__fields__.keys()])


def get_placeholders(model) -> str:
    return ("%s, " * len(tuple(model.__fields__.keys())))[:-2]


def __get_where_clause(
    filters, table_name: str, include_where: bool = True
) -> tuple[str, tuple]:
    where: list[str] = []
    bind_params: list[Any] = []

    if not filters:
        return ("", ())

    filters_iter = iter(filters)

    for k, v in filters_iter:
        if v:
            # handling special case 'tags'
            if k == "tags":
                where.append(f"{table_name}.{k} @> %s")
                bind_params.append(v)
            elif k[-5:] == "_from":
                where.append(f"{table_name}.{k[:-5]} >= %s")
                bind_params.append(v)
            elif k[-3:] == "_to":
                where.append(f"{table_name}.{k[:-3]} <= %s")
                bind_params.append(v)
            else:
                where.append(f'{table_name}.{k} IN ({ ("%s, " * len(v))[:-2] })')
                bind_params += v

    where_clause: str = ""
    if where and include_where:
        where_clause = "WHERE "

    for x in where:
        where_clause += x + " AND "

    return (where_clause[:-4], tuple(bind_params))


############
#  MODELS  #
############
MODEL_COLS = get_fields(Model)
MODEL_PLACEHOLDERS = get_placeholders(Model)


def get_type(json_data_type: str) -> str:
    """
    Maps a python type to a column data type
    """
    return {
        "string": "STRING",
        "integer": "INT8",
        "datetime": "TIMESTAMPTZ",
        "date": "DATE",
    }[json_data_type]


def get_all_models() -> list[Model]:
    return execute_stmt(
        f"""
        SELECT {MODEL_COLS} 
        FROM internal.models
        ORDER BY name""",
        (),
        Model,
        True,
    )


def get_model(name: str) -> Model:
    return execute_stmt(
        f"""
        SELECT {MODEL_COLS} 
        FROM internal.models
        WHERE name = %s""",
        (name,),
        Model,
    )


def create_model(model: Model) -> Model | None:
    def get_type(x):
        return {"markdown": "STRING", "enum": "STRING", "timestamp": "TIMESTAMPTZ"}.get(
            x, x
        )

    # build the CREATE TABLE stmt
    additions: dict[str, str] = {}

    if model.name.lower() in RESERVED_WORDS:
        print(model.name, "in reserved words list")
        # TODO raise exeption
        return None

    for f in model.skema.fields:
        if f["name"].lower() in RESERVED_WORDS:
            # TODO raise error as name is in reserved word list
            print(f["name"], "in reserved words list")
            return None

        # # check if the model allows for null
        # if f["nullable"]:
        #     # we pick the 1st item in the list
        #     additions[k] = get_type(v["anyOf"][0]["type"])
        # else:
        #     additions[k] = get_type(v["type"])

        additions[f["name"]] = get_type(f["type"])

    stmt = ""

    for k, v in additions.items():
        stmt += f"{k} {v},\n"

    stmt_prefix = f"""
    CREATE TABLE {model.name}(
        -- pk
        id UUID NOT NULL,
        -- default fields
        name STRING NULL,
        owned_by STRING NULL,
        permissions STRING NULL,
        tags STRING [] NULL DEFAULT ARRAY[],
        parent_type STRING NULL,
        parent_id UUID NULL,
        attachments STRING[] NULL DEFAULT ARRAY[],
        -- custom fields
    """

    stmt_suffix = f"""
        -- audit info
        created_at TIMESTAMPTZ NOT NULL,
        created_by STRING NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        updated_by STRING NULL,
        -- pk
        CONSTRAINT pk PRIMARY KEY (id)
        );
        CREATE INDEX {model.name}_parent ON {model.name}(parent_type, parent_id);
        CREATE INVERTED INDEX {model.name}_tags_gin ON {model.name}(tags);
    """

    # execute CREATE TABLE
    execute_stmt(
        stmt_prefix + stmt + stmt_suffix,
        (),
        returning_rs=False,
    )

    new_model = execute_stmt(
        f"""
        INSERT INTO internal.models 
            ({MODEL_COLS}) 
        VALUES 
            ({MODEL_PLACEHOLDERS})
        RETURNING {MODEL_COLS}""",
        (*tuple(model.model_dump().values()),),
        Model,
    )

    # trigger async App restart
    update_watch()

    return new_model


def update_model(model: Model) -> Model | None:
    old_model = get_model(model.name)

    print(old_model)
    print(model.name)

    additions: dict[str, str] = {}
    removals: list[str] = []

    for k in old_model.fields.properties.keys():
        if k not in model.fields.properties.keys():
            removals.append(k)

    for k, v in model.fields.properties.items():
        if k not in old_model.fields.properties.keys():
            additions[k] = v["type"]

    # drop column stmts have to be executed in their own transaction
    for x in removals:
        execute_stmt(
            f"""SET sql_safe_updates = false;
            ALTER TABLE {model.name} DROP COLUMN {x};
            SET sql_safe_updates = true;
            """,
            returning_rs=False,
        )

    for x, y in additions.items():
        execute_stmt(
            f"ALTER TABLE {model.name} ADD COLUMN {x} {get_type(y)};",
            returning_rs=False,
        )

    new_model = execute_stmt(
        f"""
        UPDATE internal.models SET
            (skema, updated_by, updated_at) = (%s, %s, %s)
        WHERE name = %s 
        RETURNING {MODEL_COLS}""",
        (model.skema.model_dump_json(), model.updated_by, model.updated_at, model.name),
        Model,
    )

    # trigger async App restart
    update_watch()

    return new_model


def delete_model(model_name: str) -> Model | None:
    # drop table
    execute_stmt(
        f"""SET sql_safe_updates = false;
        DROP TABLE {model_name};
        SET sql_safe_updates = true;
        """,
        returning_rs=False,
    )

    deleted_model = execute_stmt(
        f"""
        DELETE FROM internal.models 
        WHERE name = %s 
        RETURNING {MODEL_COLS}""",
        (model_name,),
        Model,
    )

    # trigger async App restart
    update_watch()

    return deleted_model


#############
#  REPORTS  #
#############
REPORT_COLS = get_fields(Report)
REPORT_PLACEHOLDERS = get_placeholders(Report)


def get_all_reports() -> list[Report]:
    return execute_stmt(
        f"""
        SELECT {REPORT_COLS} 
        FROM internal.reports
        ORDER BY name""",
        (),
        Report,
        True,
    )


def get_report(name: str) -> Report | None:
    return execute_stmt(
        f"""
        SELECT {REPORT_COLS} 
        FROM internal.reports
        WHERE name = %s""",
        (name,),
        Report,
    )


def create_report(report: Report) -> Report | None:
    return execute_stmt(
        f"""
        INSERT INTO internal.reports 
            ({REPORT_COLS}) 
        VALUES 
            ({REPORT_PLACEHOLDERS})
        RETURNING {REPORT_COLS}""",
        (*tuple(report.model_dump().values()),),
        Report,
    )


def update_report(report: Report) -> Report | None:
    return execute_stmt(
        f"""
        UPDATE internal.reports SET 
            sql_stmt = %s,
            updated_by = %s,
            updated_at = %s
        WHERE name = %s
        RETURNING {REPORT_COLS}""",
        (report.sql_stmt, report.updated_by, report.updated_at, report.name),
        Report,
    )


def delete_report(name: str) -> Report | None:
    return execute_stmt(
        f"""
        DELETE FROM internal.reports 
        WHERE name = %s 
        RETURNING {REPORT_COLS}""",
        (name,),
        Report,
    )


###############
#  INSTANCES  #
###############
def get_all_instances(model_name: str) -> list[Type[BaseFields]]:
    return execute_stmt(
        f"""
        SELECT *
        FROM {model_name}
        ORDER BY name
        """,
        (),
        pyd_models[model_name]["overview"],
        True,
    )


def get_instance(model_name: str, id: UUID) -> Type[BaseFields] | None:
    return execute_stmt(
        f"""
        SELECT *
        FROM {model_name}
        WHERE id = %s
        """,
        (id,),
        pyd_models[model_name]["default"],
    )


def get_all_children(
    model_name: str,
    id: UUID,
) -> dict[str, list[Type[BaseFields]]] | None:
    models = get_all_models()

    children = {}

    for m in models:
        children[m.name] = execute_stmt(
            f"""
            SELECT *
            FROM {m.name}
            WHERE (parent_type, parent_id) = (%s, %s)
            """,
            (model_name, id),
            pyd_models[m.name]["overview"],
            True,
        )

    return children


def set_parent_to_null(
    model_name: str,
    id: UUID,
) -> None:
    models = get_all_models()

    for m in models:
        execute_stmt(
            f"""
            UPDATE {m.name}
            SET parent_type = NULL, parent_id = NULL
            WHERE (parent_type, parent_id) = (%s, %s)
            """,
            (model_name, id),
            returning_rs=False,
        )

    return


def get_all_children_for_model(
    model_name: str,
    id: UUID,
    children_model_name: str,
) -> list[Type[BaseFields]] | None:
    return execute_stmt(
        f"""
            SELECT *
            FROM {children_model_name}
            WHERE (parent_type, parent_id) = (%s, %s)
            """,
        (model_name, id),
        pyd_models[children_model_name]["overview"],
        True,
    )


def get_parent_chain(
    model_name: str,
    id: UUID,
) -> list | None:
    chain = []

    p = execute_stmt(
        f"""
        SELECT parent_type, parent_id::STRING, name
        FROM {model_name}
        WHERE id = %s
        """,
        (id,),
    )

    if p[0]:
        chain.extend(get_parent_chain(p[0], p[1]))
        chain.append(p)

    else:
        chain.append(p)

    # print(chain)
    return chain


def create_instance(
    model_name: str, model_instance: Type[BaseFields]
) -> Type[BaseFields] | None:
    cols = get_fields(pyd_models[model_name]["default"])
    ph = get_placeholders(pyd_models[model_name]["default"])

    return execute_stmt(
        f"""
        INSERT INTO {model_name}
            ({cols})
        VALUES
            ({ph})
        RETURNING {cols}
        """,
        tuple(model_instance.model_dump().values()),
        pyd_models[model_name]["default"],
    )


def update_instance(
    model_name: str, model_instance: Type[BaseFields]
) -> Type[BaseFields] | None:
    cols = get_fields(pyd_models[model_name]["default"])
    ph = get_placeholders(pyd_models[model_name]["default"])

    if model_instance.id:
        old_model_instance = get_instance(model_name, model_instance.id)
    else:
        return None

    if old_model_instance:
        old_model_instance = pyd_models[model_name]["default"](
            **old_model_instance.model_dump()
        )
        update_data = model_instance.model_dump(exclude_unset=True)
        new_model_instance = old_model_instance.model_copy(update=update_data)

        return execute_stmt(
            f"""
            UPDATE {model_name} SET
                ({cols}) = ({ph})
            WHERE id = %s
            RETURNING {cols}
            """,
            (*tuple(new_model_instance.model_dump().values()), model_instance.id),
            pyd_models[model_name]["default"],
        )


def partial_update_instance(
    model_name: str, user_id: str, id: UUID, field: str, value, ts: dt.datetime
) -> Type[BaseFields] | None:
    cols = get_fields(pyd_models[model_name]["default"])

    return execute_stmt(
        f"""
        UPDATE {model_name} SET
            {field} = %s,
            updated_by = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING {cols}
        """,
        (value, user_id, ts, id),
        pyd_models[model_name]["default"],
    )


def delete_instance(model_name: str, id: UUID) -> Type[BaseFields] | None:
    cols = get_fields(pyd_models[model_name]["default"])
    return execute_stmt(
        f"""
        DELETE FROM {model_name}
        WHERE id = %s
        RETURNING {cols}
        """,
        (id,),
        pyd_models[model_name]["default"],
    )


###############
# ATTACHMENTS #
###############
def add_attachment(model_name: str, id: UUID, s3_object_name: str) -> list[str]:
    return execute_stmt(
        f"""
        UPDATE {model_name} SET
            attachments = array_append(attachments, %s)
        WHERE id = %s
        RETURNING attachments
        """,
        (s3_object_name, id),
    )


def remove_attachment(model_name: str, id: UUID, s3_object_name: str) -> list[str]:
    return execute_stmt(
        f"""
        UPDATE {model_name} SET
            attachments = array_remove(attachments, %s)
        WHERE id = %s
        RETURNING attachments
        """,
        (s3_object_name, id),
    )


# ======================================================
class DictJsonbDumper(JsonbDumper):
    def dump(self, obj):
        return super().dump(Jsonb(obj))


def execute_stmt(
    stmt: str,
    bind_args: tuple = (),
    returning_model: Type[BaseFields] = None,
    is_list: bool = False,
    returning_rs: bool = True,
) -> Type[BaseFields] | list[Type[BaseFields]] | list[tuple] | None:
    with pool.connection() as conn:
        # convert a set to a psycopg list
        conn.adapters.register_dumper(set, ListDumper)
        conn.adapters.register_dumper(dict, DictJsonbDumper)

        with conn.cursor() as cur:
            try:
                cur.execute(stmt, bind_args)  # type: ignore

                if not returning_rs:
                    return

                if not cur.description:
                    raise ValueError("Could not fetch column names from ResultSet")
                col_names = [desc[0] for desc in cur.description]

                if is_list:
                    rsl = cur.fetchall()

                    if returning_model:
                        return [
                            returning_model(
                                **{k: rs[i] for i, k in enumerate(col_names)}
                            )
                            for rs in rsl
                        ]
                    else:
                        return rsl
                else:
                    rs = cur.fetchone()
                    if rs:
                        if returning_model:
                            return returning_model(
                                **{k: rs[i] for i, k in enumerate(col_names)}
                            )
                        else:
                            return rs
                    else:
                        return None
            except Exception as e:
                # TODO correctly handle error such as PK violations
                print(e)
                return None


###########
#   SQL   #
###########
def execute_sql(
    user_type: str,
    stmt: str,
    bind_params: tuple,
) -> dict[str, Any] | None:
    if user_type == "dml":
        conn = dml_pool.getconn()
    else:
        conn = select_pool.getconn()

    conn.adapters.register_dumper(set, ListDumper)
    conn.adapters.register_dumper(dict, DictJsonbDumper)

    with conn.cursor() as cur:
        try:
            cur.execute(stmt, bind_params)  # type: ignore

            if not cur.description:
                return {"status": cur.statusmessage, "cols": [], "rows": []}

            col_names = [desc[0] for desc in cur.description]

            rsl = cur.fetchall()

            return {"status": cur.statusmessage, "cols": col_names, "rows": rsl}

        except Exception as e:
            # TODO correctly handle error such as PK violations
            return {"status": str(e), "cols": [], "rows": []}

        finally:
            if user_type == "dml":
                dml_pool.putconn(conn)
            else:
                select_pool.putconn(conn)
