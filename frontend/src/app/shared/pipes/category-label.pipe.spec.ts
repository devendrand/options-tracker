import { TestBed } from '@angular/core/testing';
import { CategoryLabelPipe } from './category-label.pipe';
import { TransactionCategory } from '@core/models/transaction.model';

describe('CategoryLabelPipe', () => {
  let pipe: CategoryLabelPipe;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [CategoryLabelPipe] });
    pipe = TestBed.inject(CategoryLabelPipe);
  });

  it('should transform OPTIONS_SELL_TO_OPEN to "Sell to Open"', () => {
    expect(pipe.transform('OPTIONS_SELL_TO_OPEN')).toBe('Sell to Open');
  });

  it('should transform OPTIONS_BUY_TO_OPEN to "Buy to Open"', () => {
    expect(pipe.transform('OPTIONS_BUY_TO_OPEN')).toBe('Buy to Open');
  });

  it('should transform OPTIONS_BUY_TO_CLOSE to "Buy to Close"', () => {
    expect(pipe.transform('OPTIONS_BUY_TO_CLOSE')).toBe('Buy to Close');
  });

  it('should transform OPTIONS_SELL_TO_CLOSE to "Sell to Close"', () => {
    expect(pipe.transform('OPTIONS_SELL_TO_CLOSE')).toBe('Sell to Close');
  });

  it('should transform OPTIONS_EXPIRED to "Expired"', () => {
    expect(pipe.transform('OPTIONS_EXPIRED')).toBe('Expired');
  });

  it('should transform OPTIONS_ASSIGNED to "Assigned"', () => {
    expect(pipe.transform('OPTIONS_ASSIGNED')).toBe('Assigned');
  });

  it('should transform OPTIONS_EXERCISED to "Exercised"', () => {
    expect(pipe.transform('OPTIONS_EXERCISED')).toBe('Exercised');
  });

  it('should transform EQUITY_BUY to "Buy"', () => {
    expect(pipe.transform('EQUITY_BUY')).toBe('Buy');
  });

  it('should transform EQUITY_SELL to "Sell"', () => {
    expect(pipe.transform('EQUITY_SELL')).toBe('Sell');
  });

  it('should transform DIVIDEND to "Dividend"', () => {
    expect(pipe.transform('DIVIDEND')).toBe('Dividend');
  });

  it('should transform TRANSFER to "Transfer"', () => {
    expect(pipe.transform('TRANSFER')).toBe('Transfer');
  });

  it('should transform INTEREST to "Interest"', () => {
    expect(pipe.transform('INTEREST')).toBe('Interest');
  });

  it('should transform FEE to "Fee"', () => {
    expect(pipe.transform('FEE')).toBe('Fee');
  });

  it('should transform JOURNAL to "Journal"', () => {
    expect(pipe.transform('JOURNAL')).toBe('Journal');
  });

  it('should transform OTHER to "Other"', () => {
    expect(pipe.transform('OTHER')).toBe('Other');
  });

  it('should return empty string for empty string input', () => {
    expect(pipe.transform('')).toBe('');
  });

  it('should return empty string for null input', () => {
    expect(pipe.transform(null)).toBe('');
  });

  it('should return empty string for undefined input', () => {
    expect(pipe.transform(undefined)).toBe('');
  });

  it('should return the raw value when category has no label mapping', () => {
    expect(pipe.transform('UNKNOWN_CATEGORY' as TransactionCategory)).toBe('UNKNOWN_CATEGORY');
  });

  it('should cover all 15 TransactionCategory values', () => {
    const categories: TransactionCategory[] = [
      'OPTIONS_SELL_TO_OPEN',
      'OPTIONS_BUY_TO_OPEN',
      'OPTIONS_BUY_TO_CLOSE',
      'OPTIONS_SELL_TO_CLOSE',
      'OPTIONS_EXPIRED',
      'OPTIONS_ASSIGNED',
      'OPTIONS_EXERCISED',
      'EQUITY_BUY',
      'EQUITY_SELL',
      'DIVIDEND',
      'TRANSFER',
      'INTEREST',
      'FEE',
      'JOURNAL',
      'OTHER',
    ];
    expect(categories.every((c) => pipe.transform(c) !== '')).toBe(true);
  });
});
