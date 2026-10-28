# Person 1. Postgres access for every service that has DATABASE_URL.
#
# ConnectionPool min 1 max 4 from DATABASE_URL.
# connection() context manager yields a connection and commits.
# ping() runs SELECT 1. Readiness probes call this.
