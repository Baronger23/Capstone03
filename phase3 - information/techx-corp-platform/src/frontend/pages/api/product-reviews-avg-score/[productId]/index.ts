// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import type { NextApiRequest, NextApiResponse } from 'next';
import { status as GrpcStatus, type ServiceError } from '@grpc/grpc-js';
import { context, trace } from '@opentelemetry/api';
import InstrumentationMiddleware from '../../../../utils/telemetry/InstrumentationMiddleware';
import { Empty, ProductReview } from '../../../../protos/demo';
import ProductReviewService from '../../../../services/ProductReview.service';

type TResponse = string | Empty | { error: string };

const isDependencyUnavailable = (error: unknown): error is ServiceError =>
    typeof error === 'object' && error !== null && 'code' in error &&
    ((error as ServiceError).code === GrpcStatus.DEADLINE_EXCEEDED || (error as ServiceError).code === GrpcStatus.UNAVAILABLE);

const handler = async ({ method, query }: NextApiRequest, res: NextApiResponse<TResponse>) => {

    switch (method) {
        case 'GET': {
            const { productId = '' } = query;

            try {
                const averageScore = await ProductReviewService.getAverageProductReviewScore(productId as string);
                return res.status(200).json(averageScore);
            } catch (error) {
                // PM-0016: same rationale as pages/api/product-reviews/[productId] — don't
                // collapse a timed-out dependency into a fabricated score.
                if (isDependencyUnavailable(error)) {
                    trace.getSpan(context.active())?.setAttribute('app.product_reviews.degraded', true);
                    return res.status(503).json({ error: 'DEPENDENCY_UNAVAILABLE' });
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
