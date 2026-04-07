import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should have title "options-tracker-ui"', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app.title).toBe('options-tracker-ui');
  });

  it('should render the navigation bar', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const nav = fixture.nativeElement.querySelector('nav.app-nav');
    expect(nav).toBeTruthy();
  });

  it('should render brand link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const brand = fixture.nativeElement.querySelector('.app-nav__brand');
    expect(brand).toBeTruthy();
    expect(brand.textContent.trim()).toBe('Options Tracker');
  });

  it('should render all four navigation links', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const links = fixture.nativeElement.querySelectorAll('.app-nav__links a');
    expect(links.length).toBe(4);
  });

  it('should have correct href for Dashboard link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="nav-dashboard"]');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/dashboard');
  });

  it('should not render Upload nav link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="nav-upload"]');
    expect(link).toBeNull();
  });

  it('should have correct href for Transactions link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="nav-transactions"]');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/transactions');
  });

  it('should have correct href for Positions link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="nav-positions"]');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/positions');
  });

  it('should have correct href for Upload History link', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const link = fixture.nativeElement.querySelector('[data-testid="nav-upload-history"]');
    expect(link).toBeTruthy();
    expect(link.getAttribute('href')).toBe('/upload-history');
  });

  it('should render a main content area', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const main = fixture.nativeElement.querySelector('main.app-content');
    expect(main).toBeTruthy();
  });
});
