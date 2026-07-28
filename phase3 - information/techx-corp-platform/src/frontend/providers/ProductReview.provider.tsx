// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { createContext, useContext, useEffect, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import ApiGateway from '../gateways/Api.gateway';
import { ProductReview } from '../protos/demo';

interface IContext {
    // null = not loaded yet; [] = loaded with no reviews; array = loaded with reviews.
    productReviews: ProductReview[] | null;
    loading: boolean;
    error: Error | null;
    averageScore: string | null;
}

export const Context = createContext<IContext>({
    productReviews: null,
    loading: false,
    error: null,
    averageScore: null,
});

interface IProps {
    children: React.ReactNode;
    productId: string;
}

//export const useProductReview = () => useContext(Context);
export const useProductReview = () => {
    const value = useContext(Context);
    return value;
};

// PM-0016 review: react-query's default retry (3x, exponential backoff) would
// hammer an already-degraded product-reviews dependency — a single widget open
// could fire up to 4 attempts x 2 queries = 8 requests during exactly the outage
// this 503 is signaling. Never retry a classified DEPENDENCY_UNAVAILABLE (see
// utils/Request.ts, which tags it with `.status`); still allow a couple of
// retries for other/transient failures.
const retryUnlessDependencyUnavailable = (failureCount: number, error: unknown) =>
    (error as { status?: number })?.status !== 503 && failureCount < 2;

const ProductReviewProvider = ({ children, productId }: IProps) => {
    const {
        data,
        isLoading,
        isFetching,
        isError,
        error,
        isSuccess,
    } = useQuery<ProductReview[]>({
        queryKey: ['productReviews', productId],
        queryFn: () => ApiGateway.getProductReviews(productId),
        refetchOnWindowFocus: false,
        retry: retryUnlessDependencyUnavailable,
    });

    // Use a sentinel: null while loading, [] if loaded but empty, array when loaded with data.
    const productReviews: ProductReview[] | null = isSuccess
        ? Array.isArray(data)
            ? data
            : []
        : null;

    const loading = isLoading || isFetching;

    // Narrow react-query's `unknown` error to `Error | null`.
    const currentError: Error | null = isError
        ? error instanceof Error
            ? error
            : new Error('Unknown error')
        : null;

    const { data: averageScore = '' } = useQuery({
        queryKey: ['productReviewAvgScore', productId],
        queryFn: () => ApiGateway.getAverageProductReviewScore(productId),
        retry: retryUnlessDependencyUnavailable,
    });

    const value = useMemo(
        () => ({
            productReviews,
            loading,
            error: currentError,
            averageScore,
        }),
        [productReviews, loading, currentError, averageScore]
    );

    return <Context.Provider value={value}>{children}</Context.Provider>;
};

export default ProductReviewProvider;
