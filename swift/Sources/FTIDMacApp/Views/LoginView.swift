import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var model: AppModel
    @State private var userID = ""
    @State private var passcode = ""
    @FocusState private var focusedField: Field?

    private enum Field { case userID, passcode, submit }

    private var trimmedUserID: String {
        userID.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var canSubmit: Bool {
        !trimmedUserID.isEmpty && !passcode.isEmpty && !model.isWorking
    }

    private func submit() {
        guard canSubmit else { return }
        Task { await model.login(userID: trimmedUserID, passcode: passcode) }
    }

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.11, green: 0.16, blue: 0.28),
                    Color(red: 0.15, green: 0.32, blue: 0.33),
                    Color(red: 0.31, green: 0.23, blue: 0.15),
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            VStack(spacing: 28) {
                VStack(spacing: 12) {
                    Image(systemName: "shippingbox.circle.fill")
                        .font(.system(size: 68))
                        .foregroundStyle(.white)
                    Text("FTID Generator")
                        .font(.system(size: 34, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)
                    Text("Native macOS front end, bundled Python backend.")
                        .font(.headline)
                        .foregroundStyle(.white.opacity(0.84))
                }

                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("User ID")
                            .font(.headline)
                        TextField("Enter your User ID", text: $userID)
                            .textFieldStyle(.roundedBorder)
                            .focused($focusedField, equals: .userID)
                            .onSubmit { focusedField = .passcode }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("Passcode")
                            .font(.headline)
                        SecureField("Enter your passcode", text: $passcode)
                            .textFieldStyle(.roundedBorder)
                            .focused($focusedField, equals: .passcode)
                            .onSubmit(submit)
                    }

                    Button(action: submit) {
                        HStack(spacing: 8) {
                            if model.isWorking {
                                ProgressView()
                                    .controlSize(.small)
                            }
                            Text(model.isWorking ? "Signing In…" : "Sign In")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .keyboardShortcut(.defaultAction)
                    .focusable()
                    .focused($focusedField, equals: .submit)
                    .onKeyPress(.space) {
                        submit()
                        return .handled
                    }
                    .disabled(!canSubmit)
                }
                .padding(28)
                .frame(maxWidth: 420)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 26, style: .continuous))
            }
            .padding(32)
        }
        .onAppear { focusedField = .userID }
    }
}
