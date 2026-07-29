# Checkout Rollout Ownership Design

## Problem

The live `checkout` Service currently selects four ready endpoints: two pods
owned by the source Deployment and two pods owned by `checkout-rollout`.
Although the Rollout uses `workloadRef.scaleDown: progressively`, the source
Deployment still declares two replicas. This dilutes the configured canary
weights and keeps duplicate steady-state capacity.

## Design

Set `components.checkout.replicasManagedExternally: true` in the production
values. The rendered source Deployment will retain its pod template but omit
`spec.replicas`. The rendered Rollout already omits `spec.replicas` through its
existing `rollouts.checkout.replicasManagedExternally: true` setting, while
`checkout-hpa` continues to target the Rollout scale subresource with a
two-replica minimum.

After the PR is merged and Argo CD is Synced/Healthy at its merge revision,
perform one explicitly approved migration action:

```bash
kubectl scale deployment checkout -n techx-tf3 --replicas=0
```

Argo CD already ignores the Deployment replica field, so reconciliation must
not restore duplicate replicas. The Rollout remains able to scale the source
Deployment during its workload-reference rollback behavior.

## Verification

- A render contract must fail before the change because the checkout Deployment
  contains `spec.replicas`.
- The exact Argo CD Helm render must show:
  - checkout Deployment without `spec.replicas`;
  - checkout Rollout without `spec.replicas` and with
    `workloadRef.scaleDown: progressively`;
  - checkout HPA targeting `checkout-rollout` with `minReplicas: 2`;
  - no change to the checkout pod template, image, probes, resources,
    scheduling, feature flags, or MSK configuration.
- Before the one-time scale, Argo CD must be Synced/Healthy at the merge
  revision and the two Rollout pods must be Ready.
- After the scale, the source Deployment must remain at zero and the checkout
  EndpointSlice must contain exactly two Ready Rollout-owned pod IPs.
- Checkout success ratio, p95 latency, Rollout health, HPA, PDB, pod restarts,
  and recent errors must remain healthy.

## Rollback

If the Rollout pods or checkout SLO degrade, scale the source Deployment back to
two replicas. Revert the PR only if Argo CD must resume declaring the source
Deployment replica count.

## Scope

This change only corrects Deployment/Rollout replica ownership. It does not
migrate checkout to ARM and does not modify Envoy, flagd, `/flagservice`,
fault injection, checkout business logic, traffic routing, HPA thresholds, or
canary analysis queries.
