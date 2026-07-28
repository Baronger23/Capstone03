#!/bin/sh
set -eu

# Safe defaults keep non-production chart users in shadow mode. Production
# promotes these values explicitly through values-prod.yaml envOverrides.
: "${BROWSE_RATE_LIMIT_MAX_TOKENS:=100}"
: "${BROWSE_RATE_LIMIT_TOKENS_PER_FILL:=50}"
: "${BROWSE_RATE_LIMIT_FILL_INTERVAL:=1s}"
: "${BROWSE_RATE_LIMIT_ENABLED_PERCENT:=100}"
: "${BROWSE_RATE_LIMIT_ENFORCED_PERCENT:=0}"
: "${LOCAL_RATE_LIMIT_ENABLED_PERCENT:=100}"
: "${LOCAL_RATE_LIMIT_ENFORCED_PERCENT:=0}"

export BROWSE_RATE_LIMIT_MAX_TOKENS
export BROWSE_RATE_LIMIT_TOKENS_PER_FILL
export BROWSE_RATE_LIMIT_FILL_INTERVAL
export BROWSE_RATE_LIMIT_ENABLED_PERCENT
export BROWSE_RATE_LIMIT_ENFORCED_PERCENT
export LOCAL_RATE_LIMIT_ENABLED_PERCENT
export LOCAL_RATE_LIMIT_ENFORCED_PERCENT

envsubst < envoy.tmpl.yaml > envoy.yaml
envoy --mode validate -c envoy.yaml
exec envoy -c envoy.yaml
