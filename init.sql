CREATE TABLE files (
	fileid BIGSERIAL UNIQUE,
	filename text NOT NULL,
	mime text NOT NULL,
	extension text NOT NULL,
	bytes bigint NOT NULL,
	uploader bigint,
	owner bigint,
	public boolean NOT NULL,
	readgroups bigint[] NOT NULL,
	writegroups bigint[] NOT NULL,
	uploaded timestamp NOT NULL,
	tags text[] NOT NULL,
	sha256 char(64) NOT NULL,
	description text
);

CREATE TABLE users (
	userid BIGSERIAL UNIQUE,
	username text UNIQUE NOT NULL,
	admin boolean NOT NULL,
	salt text NOT NULL,
	hash text NOT NULL,
	registered timestamp NOT NULL,
	groups bigint[] NOT NULL
);

INSERT INTO users (username, admin, salt, hash, registered, groups) VALUES (
	'system',
	true,
	'',
	'',
	TIMESTAMP 'now',
	'{1}'
);

INSERT INTO users (username, admin, salt, hash, registered, groups) VALUES (
	'Anonymous',
	false,
	'',
	'',
	TIMESTAMP 'now',
	'{1}'
);

CREATE TABLE groups (
	groupid BIGSERIAL UNIQUE,
	groupname text UNIQUE NOT NULL,
	creator bigint NOT NULL,
	leader bigint NOT NULL
);

INSERT INTO groups (groupname, creator, leader) VALUES (
	'All',
	1,
	1
);
