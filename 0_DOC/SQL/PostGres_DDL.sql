CREATE TABLE public.langchain_pg_collection (
	name varchar NULL,
	cmetadata json NULL,
	uuid uuid NOT NULL,
	user_id varchar(20) NULL,
	CONSTRAINT langchain_pg_collection_pkey PRIMARY KEY (uuid),
	CONSTRAINT unique_name_user UNIQUE (name, user_id)
);


CREATE TABLE public.langchain_pg_embedding (
	collection_id uuid NULL,
	embedding public.vector NULL,
	"document" varchar NULL,
	cmetadata json NULL,
	custom_id varchar NULL,
	"uuid" uuid NOT NULL,
	CONSTRAINT langchain_pg_embedding_pkey PRIMARY KEY (uuid),
	CONSTRAINT langchain_pg_embedding_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.langchain_pg_collection("uuid") ON DELETE CASCADE
);
