// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import { status as GrpcStatus, type ServiceError } from '@grpc/grpc-js';
import { context, trace } from '@opentelemetry/api';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import { Empty, ProductReview } from '../../../../protos/demo';
import ProductReviewService from '../../../../services/ProductReview.service';

type TResponse = ProductReview[] | Empty | string;

const isDependencyUnavailable = (error: unknown): error is ServiceError =>
    typeof error === 'object' && error !== null && 'code' in error &&
    ((error as ServiceError).code === GrpcStatus.DEADLINE_EXCEEDED || (error as ServiceError).code === GrpcStatus.UNAVAILABLE);

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {

    switch (method) {
        case 'GET': {
            const { productId = '' } = query;

            try {
                const productReviews = await ProductReviewService.getProductReviews(productId as string);
                return res.status(200).json(productReviews);
            } catch (error) {
                // PM-0016: a timed-out/unavailable product-reviews dependency is NOT the same
                // as "no reviews for this product" — [] already has that meaning (REL-review
                // semantics), so we must not collapse the two into a silent 200. Surface a
                // stable 503 so the widget/provider can distinguish "degraded" from "empty",
                // and keep the failure visible to SLO signal instead of masking it as success.
                //
                // Review round 2: the body is deliberately PLAIN TEXT, not JSON. frontend
                // rolls out with maxUnavailable:0/maxSurge:1, so old and new pods (old and
                // new client bundles) coexist during rollout. utils/Request.ts unconditionally
                // JSON.parse()s any non-empty body regardless of status in EVERY version of
                // this codebase — an old client hitting this new 503 with a JSON `{error}`
                // body would parse it successfully and treat it as data, reintroducing the
                // exact silent-empty-state bug this fix exists to prevent (see
                // ProductReview.provider.tsx: non-array data -> []). A non-JSON body makes
                // JSON.parse throw on old AND new clients alike, so both correctly reject
                // instead of one silently "succeeding". This is not a response contract old
                // clients can consume either way, so plain text costs nothing.
                if (isDependencyUnavailable(error)) {
                    trace.getSpan(context.active())?.setAttribute('app.product_reviews.degraded', true);
                    return res.status(503).send('DEPENDENCY_UNAVAILABLE');
                }
                throw error;
            }
        }

        default: {
            return res.status(405).send('');
        }
    }
};

export default InstrumentationMiddleware(handler);
