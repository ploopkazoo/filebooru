CREATE TABLE files (
	fileid BIGSERIAL,
	filename text NOT NULL,
	bytes bigint NOT NULL,
	uploader bigint,
	owner bigint,
	readgroups bigint[] NOT NULL,
	writegroups bigint[] NOT NULL,
	uploaded timestamp NOT NULL,
	tags text[] NOT NULL,
	sha256 char(64) NOT NULL
);

CREATE TABLE users (
	userid BIGSERIAL,
	username text UNIQUE NOT NULL,
	salt text NOT NULL,
	hash text NOT NULL,
	registered timestamp NOT NULL,
	groups bigint[] NOT NULL
);

CREATE TABLE groups (
	groupid BIGSERIAL,
	groupname text UNIQUE NOT NULL,
	creator bigint NOT NULL,
	leader bigint NOT NULL
);
