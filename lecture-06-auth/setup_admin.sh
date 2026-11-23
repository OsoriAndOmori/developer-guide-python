#!/bin/bash
# 관리 화면(http://localhost:8083)을 브라우저에서 열 수 있게 master realm 의 HTTPS 요구를 끈다. (개발용, 한 번만)
# Docker Desktop 에서는 브라우저 요청이 "외부"로 보여서 기본 설정이면 "HTTPS required" 가 뜬다.
docker exec lecture06-keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin --password admin \
&& docker exec lecture06-keycloak /opt/keycloak/bin/kcadm.sh update realms/master -s sslRequired=NONE \
&& echo "OK: http://localhost:8083 (admin / admin)"
