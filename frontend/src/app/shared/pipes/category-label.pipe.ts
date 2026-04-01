import { Pipe, PipeTransform } from '@angular/core';
import { TransactionCategory } from '@core/models/transaction.model';

const CATEGORY_LABELS: Record<TransactionCategory, string> = {
  OPTIONS_SELL_TO_OPEN: 'Sell to Open',
  OPTIONS_BUY_TO_OPEN: 'Buy to Open',
  OPTIONS_BUY_TO_CLOSE: 'Buy to Close',
  OPTIONS_SELL_TO_CLOSE: 'Sell to Close',
  OPTIONS_EXPIRED: 'Expired',
  OPTIONS_ASSIGNED: 'Assigned',
  OPTIONS_EXERCISED: 'Exercised',
  EQUITY_BUY: 'Buy',
  EQUITY_SELL: 'Sell',
  DIVIDEND: 'Dividend',
  TRANSFER: 'Transfer',
  INTEREST: 'Interest',
  FEE: 'Fee',
  JOURNAL: 'Journal',
  OTHER: 'Other',
};

@Pipe({
  name: 'categoryLabel',
  pure: true,
})
export class CategoryLabelPipe implements PipeTransform {
  transform(value: TransactionCategory | '' | null | undefined): string {
    if (!value) return '';
    return CATEGORY_LABELS[value as TransactionCategory] ?? value;
  }
}
