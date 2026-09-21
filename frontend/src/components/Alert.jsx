import { createContext, useContext } from 'react';

// Browser port of React Native Reusables Alert (MIT):
// https://github.com/founded-labs/react-native-reusables
const AlertTextContext = createContext('');

function AlertSymbol() {
  return '!';
}

export function Alert({ children, className = '', variant, icon: Icon = AlertSymbol, iconClassName = '', ...props }) {
  const textClass = variant === 'destructive' ? 'alert-destructive' : '';
  return (
    <AlertTextContext.Provider value={textClass}>
      <div className={`alert ${textClass} ${className}`} role="alert" {...props}>
        <span className={`alert-icon ${iconClassName}`} aria-hidden="true"><Icon /></span>
        <div>{children}</div>
      </div>
    </AlertTextContext.Provider>
  );
}

export function AlertTitle({ children, className = '', ...props }) {
  return <h2 className={`alert-title ${className}`} {...props}>{children}</h2>;
}

export function AlertDescription({ children, className = '', ...props }) {
  const textClass = useContext(AlertTextContext);
  return <div className={`alert-description ${textClass ? 'alert-description-destructive' : ''} ${className}`} {...props}>{children}</div>;
}
