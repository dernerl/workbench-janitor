import FoundationModels
import Foundation

let context = CommandLine.arguments.dropFirst().joined(separator: " ")

guard SystemLanguageModel.default.isAvailable else {
    FileHandle.standardError.write("Apple Intelligence model not available: \(SystemLanguageModel.default.availability)\n".data(using: .utf8)!)
    exit(1)
}

let session = LanguageModelSession(
    instructions: "Beschreibe in einem Satz (max. 20 Wörter, Deutsch), wofür dieser Ordner/dieses Projekt ist. Antworte nur mit dem Satz, ohne Einleitung."
)

do {
    let response = try await session.respond(to: context)
    print(response.content)
} catch {
    FileHandle.standardError.write("Error: \(error)\n".data(using: .utf8)!)
    exit(1)
}
