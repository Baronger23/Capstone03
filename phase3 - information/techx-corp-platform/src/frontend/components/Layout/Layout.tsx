// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import Header from '../Header';
import Footer from '../Footer';
import CopilotWidget from '../CopilotWidget';

interface IProps {
  children: React.ReactNode;
}

const Layout = ({ children }: IProps) => {
  return (
    <>
      <Header />
      <main>{children}</main>
      <Footer />
      <CopilotWidget />
    </>
  );
};

export default Layout;
